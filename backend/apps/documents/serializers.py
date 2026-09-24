from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.access import can_access
from apps.questionnaires.models import Response

from .models import DocumentPage, ExtractionResult, OCRJob, OCRResult, UploadedDocument
from .services.grouping import create_document_pages, create_response, ensure_batch_capacity
from .validation import inspect_upload


class OCRResultSerializer(serializers.ModelSerializer):
    page_number = serializers.IntegerField(source="page.page_number", read_only=True)

    class Meta:
        model = OCRResult
        fields = ("id", "page_number", "plain_text", "mean_confidence", "raw_output")


class ExtractionResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractionResult
        fields = ("parser_version", "confidence", "structured_output", "warnings")


class OCRJobSerializer(serializers.ModelSerializer):
    results = OCRResultSerializer(many=True, read_only=True)
    extraction = ExtractionResultSerializer(read_only=True)

    class Meta:
        model = OCRJob
        fields = (
            "id",
            "status",
            "engine",
            "model_version",
            "attempts",
            "started_at",
            "finished_at",
            "processing_ms",
            "error_code",
            "error_message",
            "results",
            "extraction",
        )


class ResponsePageSerializer(serializers.ModelSerializer):
    document_id = serializers.UUIDField(read_only=True)
    original_filename = serializers.CharField(source="document.original_filename", read_only=True)
    content_type = serializers.CharField(source="document.content_type", read_only=True)
    source_page_number = serializers.IntegerField(source="page_number", read_only=True)
    file_url = serializers.SerializerMethodField()
    ocr_text = serializers.SerializerMethodField()

    class Meta:
        model = DocumentPage
        fields = (
            "id",
            "response",
            "document_id",
            "original_filename",
            "content_type",
            "source_page_number",
            "original_upload_order",
            "detected_template_page_number",
            "assigned_template_page_number",
            "classification_confidence",
            "classification_method",
            "processing_status",
            "validation_issues",
            "file_url",
            "ocr_text",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_file_url(self, obj) -> str | None:
        request = self.context.get("request")
        return request.build_absolute_uri(f"/api/v1/documents/{obj.document_id}/file/") if request else None

    @extend_schema_field(serializers.CharField())
    def get_ocr_text(self, obj) -> str:
        result = obj.ocr_results.order_by("-created_at").first()
        return result.plain_text if result else ""


class ResponsePageUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentPage
        fields = ("response", "assigned_template_page_number")

    def validate_response(self, value):
        user = self.context["request"].user
        if not can_access(user, value.batch.owner_id):
            raise serializers.ValidationError("Response not found.")
        if value.batch_id != self.instance.response.batch_id:
            raise serializers.ValidationError("A page can only move between responses in the same batch.")
        if value.id != self.instance.response_id and self.instance.document.page_count > 1:
            raise serializers.ValidationError("Pages inside one PDF cannot be moved to another response individually.")
        return value

    def validate_assigned_template_page_number(self, value):
        response = self.initial_data.get("response")
        target = self.instance.response
        if response:
            try:
                target = Response.objects.get(pk=response, batch__owner=self.context["request"].user)
            except (Response.DoesNotExist, DjangoValidationError, ValueError) as exc:
                raise serializers.ValidationError("Response not found.") from exc
        if value is None or value < 1 or value > target.expected_page_count:
            raise serializers.ValidationError(f"Choose a page number from 1 to {target.expected_page_count}.")
        return value


class UploadedDocumentSerializer(serializers.ModelSerializer):
    upload = serializers.FileField(write_only=True)
    response = serializers.PrimaryKeyRelatedField(queryset=Response.objects.all(), required=False, allow_null=True)
    template_page_number = serializers.IntegerField(write_only=True, required=False, min_value=1, max_value=100)
    ocr_job = OCRJobSerializer(read_only=True)
    pages = ResponsePageSerializer(many=True, read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = UploadedDocument
        fields = (
            "id",
            "questionnaire",
            "batch",
            "response",
            "document_type",
            "upload",
            "original_filename",
            "content_type",
            "size_bytes",
            "sha256",
            "page_count",
            "grouping_mode",
            "status",
            "failure_reason",
            "download_url",
            "ocr_job",
            "pages",
            "template_page_number",
            "created_at",
        )
        read_only_fields = (
            "id",
            "original_filename",
            "content_type",
            "size_bytes",
            "sha256",
            "page_count",
            "status",
            "failure_reason",
            "download_url",
            "ocr_job",
            "pages",
            "created_at",
        )

    def validate(self, attrs):
        user = self.context["request"].user
        document_type = attrs.get("document_type")
        questionnaire = attrs.get("questionnaire")
        batch = attrs.get("batch")
        response = attrs.get("response")
        if document_type == UploadedDocument.Type.TEMPLATE:
            if not questionnaire or not can_access(user, questionnaire.owner_id) or batch or response:
                raise serializers.ValidationError("A template upload requires your questionnaire and no response batch.")
        elif document_type == UploadedDocument.Type.RESPONSE:
            if not batch or not can_access(user, batch.owner_id) or questionnaire:
                raise serializers.ValidationError("A response upload requires your response batch and no questionnaire.")
            if response and (response.batch_id != batch.id or not can_access(user, response.batch.owner_id)):
                raise serializers.ValidationError("The selected response does not belong to this batch.")
        attrs["inspection"] = inspect_upload(attrs["upload"])
        if document_type == UploadedDocument.Type.RESPONSE:
            if not response:
                ensure_batch_capacity(user, batch)
            template_page_number = attrs.get("template_page_number")
            if template_page_number and template_page_number > batch.questionnaire_version.expected_page_count:
                raise serializers.ValidationError(
                    {"template_page_number": f"This questionnaire has {batch.questionnaire_version.expected_page_count} pages."}
                )
            if template_page_number and attrs["inspection"]["page_count"] != 1:
                raise serializers.ValidationError(
                    {"template_page_number": "An explicit page assignment can only be used with a single image."}
                )
        else:
            attrs["grouping_mode"] = UploadedDocument.GroupingMode.TEMPLATE
        return attrs

    def create(self, validated_data):
        upload = validated_data.pop("upload")
        inspection = validated_data.pop("inspection")
        template_page_number = validated_data.pop("template_page_number", None)
        if validated_data["document_type"] == UploadedDocument.Type.RESPONSE and not validated_data.get("response"):
            validated_data["response"] = create_response(
                validated_data["batch"],
                user=self.context["request"].user,
            )
        document = UploadedDocument.objects.create(
            owner=self.context["request"].user,
            file=upload,
            original_filename=upload.name[:255],
            size_bytes=upload.size,
            **inspection,
            **validated_data,
        )
        create_document_pages(document, template_page_number=template_page_number)
        return document

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_download_url(self, obj) -> str | None:
        request = self.context.get("request")
        return request.build_absolute_uri(f"/api/v1/documents/{obj.id}/file/") if request else None
