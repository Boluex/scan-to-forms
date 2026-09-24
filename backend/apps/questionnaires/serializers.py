from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.access import can_access
from apps.documents.serializers import ResponsePageSerializer
from apps.documents.services.grouping import create_response

from .models import (
    Answer,
    Question,
    Questionnaire,
    QuestionnaireVersion,
    QuestionOption,
    Response,
    ResponseBatch,
    TemplatePage,
)


class TemplatePageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplatePage
        fields = ("id", "page_number", "reference_text", "anchors", "text_signature")
        read_only_fields = fields


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ("id", "key", "label", "value", "position")
        read_only_fields = ("id",)


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = (
            "id",
            "key",
            "position",
            "text",
            "help_text",
            "type",
            "required",
            "validation_rules",
            "source_region",
            "template_page_number",
            "options",
        )
        read_only_fields = ("id",)


class QuestionnaireVersionSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, required=False)
    template_pages = TemplatePageSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionnaireVersion
        fields = (
            "id",
            "version_number",
            "parse_status",
            "parser_version",
            "raw_schema",
            "expected_page_count",
            "template_pages",
            "questions",
            "created_at",
        )
        read_only_fields = ("id", "version_number", "created_at")


class QuestionnaireSerializer(serializers.ModelSerializer):
    latest_version = serializers.SerializerMethodField()

    class Meta:
        model = Questionnaire
        fields = ("id", "title", "description", "status", "source_language", "latest_version", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at", "latest_version")

    @extend_schema_field(QuestionnaireVersionSerializer(allow_null=True))
    def get_latest_version(self, obj) -> dict | None:
        version = obj.versions.prefetch_related("questions__options").first()
        return QuestionnaireVersionSerializer(version).data if version else None

    @transaction.atomic
    def create(self, validated_data):
        questionnaire = Questionnaire.objects.create(owner=self.context["request"].user, **validated_data)
        QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
        return questionnaire


class VersionCreateSerializer(serializers.Serializer):
    parse_status = serializers.ChoiceField(choices=QuestionnaireVersion.ParseStatus.choices, default="DRAFT")
    parser_version = serializers.CharField(required=False, allow_blank=True)
    raw_schema = serializers.JSONField(required=False)
    expected_page_count = serializers.IntegerField(min_value=1, max_value=100, default=1)
    questions = QuestionSerializer(many=True)

    @transaction.atomic
    def create(self, validated_data):
        questionnaire = self.context["questionnaire"]
        next_number = (questionnaire.versions.order_by("-version_number").values_list("version_number", flat=True).first() or 0) + 1
        questions = validated_data.pop("questions", [])
        version = QuestionnaireVersion.objects.create(
            questionnaire=questionnaire, version_number=next_number, **validated_data
        )
        for question_data in questions:
            options = question_data.pop("options", [])
            question = Question.objects.create(version=version, **question_data)
            QuestionOption.objects.bulk_create([QuestionOption(question=question, **option) for option in options])
        return version


class ResponseBatchSerializer(serializers.ModelSerializer):
    questionnaire_title = serializers.CharField(source="questionnaire_version.questionnaire.title", read_only=True)
    response_count = serializers.IntegerField(read_only=True)
    physical_page_count = serializers.IntegerField(read_only=True)
    expected_page_count = serializers.IntegerField(source="questionnaire_version.expected_page_count", read_only=True)

    class Meta:
        model = ResponseBatch
        fields = (
            "id",
            "questionnaire_version",
            "questionnaire_title",
            "name",
            "status",
            "response_count",
            "physical_page_count",
            "expected_page_count",
            "created_at",
        )
        read_only_fields = ("id", "status", "response_count", "physical_page_count", "expected_page_count", "created_at")

    def validate_questionnaire_version(self, value):
        if not can_access(self.context["request"].user, value.questionnaire.owner_id):
            raise serializers.ValidationError("Questionnaire version not found.")
        return value

    def create(self, validated_data):
        return ResponseBatch.objects.create(owner=self.context["request"].user, **validated_data)


class AnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.text", read_only=True)
    question_type = serializers.CharField(source="question.type", read_only=True)
    question_key = serializers.CharField(source="question.key", read_only=True)
    options = QuestionOptionSerializer(source="question.options", many=True, read_only=True)

    class Meta:
        model = Answer
        fields = (
            "id",
            "question",
            "question_key",
            "question_text",
            "question_type",
            "options",
            "value_text",
            "value_json",
            "confidence",
            "review_status",
            "provenance",
            "source_region",
            "raw_value",
            "updated_at",
        )
        read_only_fields = ("id", "question", "provenance", "confidence", "source_region", "raw_value", "updated_at")

    def validate_review_status(self, value):
        if value not in (Answer.ReviewStatus.APPROVED, Answer.ReviewStatus.REJECTED):
            raise serializers.ValidationError("Answers can only be approved or rejected during manual review.")
        return value

    def update(self, instance, validated_data):
        changed = any(key in validated_data and validated_data[key] != getattr(instance, key) for key in ("value_text", "value_json"))
        if changed:
            validated_data["provenance"] = Answer.Provenance.MANUAL
            validated_data.setdefault("review_status", Answer.ReviewStatus.CORRECTED)
        elif validated_data.get("review_status") == Answer.ReviewStatus.APPROVED:
            validated_data["provenance"] = Answer.Provenance.APPROVED
        return super().update(instance, validated_data)


class ResponseSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)
    questionnaire_title = serializers.CharField(source="batch.questionnaire_version.questionnaire.title", read_only=True)
    source_document_id = serializers.SerializerMethodField()
    pages = ResponsePageSerializer(many=True, read_only=True)
    uploaded_page_count = serializers.IntegerField(source="pages.count", read_only=True)

    class Meta:
        model = Response
        fields = (
            "id",
            "batch",
            "questionnaire_title",
            "respondent_reference",
            "sequence",
            "status",
            "expected_page_count",
            "uploaded_page_count",
            "validation_issues",
            "pages",
            "answers",
            "source_document_id",
            "confirmed_at",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_source_document_id(self, obj):
        document = obj.documents.first()
        return document.id if document else None


class ResponseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = ("id", "batch", "respondent_reference", "sequence", "expected_page_count", "status")
        read_only_fields = ("id", "sequence", "expected_page_count", "status")

    def validate_batch(self, value):
        if not can_access(self.context["request"].user, value.owner_id):
            raise serializers.ValidationError("Response batch not found.")
        return value

    def create(self, validated_data):
        batch = validated_data["batch"]
        return create_response(
            batch,
            validated_data.get("respondent_reference", ""),
            user=self.context["request"].user,
        )


class BulkGroupingSerializer(serializers.Serializer):
    file_count = serializers.IntegerField(min_value=1, max_value=5000)
