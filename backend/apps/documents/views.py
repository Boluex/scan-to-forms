from django.db import transaction
from django.http import FileResponse
from rest_framework import decorators, mixins, status, throttling, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.billing.services import reserve_pages
from apps.core.access import WorkspacePermission, owned
from apps.core.models import record_audit
from apps.core.throttles import WorkspaceUserThrottle
from apps.questionnaires.integrity import invalidate_response
from apps.questionnaires.models import Response as QuestionnaireResponse

from .models import DocumentPage, OCRJob, UploadedDocument
from .serializers import (
    ResponsePageSerializer,
    ResponsePageUpdateSerializer,
    UploadedDocumentSerializer,
)
from .services.grouping import (
    aggregate_response_answers,
    refresh_response_validation,
    update_batch_status,
)
from .tasks import process_document


class UploadThrottle(throttling.UserRateThrottle):
    permission_classes = (WorkspacePermission,)
    scope = "upload"


class UploadedDocumentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (WorkspacePermission,)
    serializer_class = UploadedDocumentSerializer
    def get_throttles(self):
        return [UploadThrottle()] if self.action == "create" else [WorkspaceUserThrottle()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UploadedDocument.objects.none()
        return (
            owned(UploadedDocument.objects.all(), self.request.user)
            .select_related("ocr_job", "response")
            .prefetch_related("pages__ocr_results")
        )

    def perform_create(self, serializer):
        from apps.orders.models import Order
        batch = serializer.validated_data.get("batch")
        questionnaire = serializer.validated_data.get("questionnaire")
        if (batch and Order.objects.filter(response_batch=batch).exists()) or (questionnaire and Order.objects.filter(questionnaire=questionnaire).exists()):
            raise ValidationError("Use this order's upload endpoint.")
        with transaction.atomic():
            reserve_pages(self.request.user, serializer.validated_data["inspection"]["page_count"])
            document = serializer.save(status=UploadedDocument.Status.QUEUED)
            job = OCRJob.objects.create(document=document)
            if document.response_id:
                update_batch_status(document.response.batch_id)
            transaction.on_commit(lambda: process_document.delay(str(job.id)))
        record_audit(actor=self.request.user, action="document.uploaded", target=document, request=self.request)

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        response_id = document.response_id
        batch_id = document.batch_id
        record_audit(actor=request.user, action="document.deleted", target=document, request=request)
        storage = document.file.storage
        name = document.file.name
        response = super().destroy(request, *args, **kwargs)
        transaction.on_commit(lambda: storage.delete(name))
        if response_id:
            invalidate_response(QuestionnaireResponse.objects.get(pk=response_id), recheck_answers=True)
            def regroup_after_delete():
                refresh_response_validation(response_id)
                aggregate_response_answers(response_id, force=True)
                update_batch_status(batch_id)

            transaction.on_commit(regroup_after_delete)
        return response

    @decorators.action(detail=True, methods=("get",), url_path="file")
    def file(self, request, pk=None):
        document = self.get_object()
        handle = document.file.open("rb")
        return FileResponse(handle, as_attachment=False, filename=document.original_filename, content_type=document.content_type)

    @decorators.action(detail=True, methods=("post",))
    def retry(self, request, pk=None):
        document = self.get_object()
        if document.order_id:
            from apps.orders.services import require_paid
            require_paid(document.order)
        if not hasattr(document, "ocr_job"):
            raise ValidationError("Start processing through the order first.")
        if document.ocr_job.status not in (OCRJob.Status.FAILED, OCRJob.Status.NEEDS_REVIEW):
            return Response({"detail": "Only failed or reviewed jobs can be reprocessed."}, status=status.HTTP_409_CONFLICT)
        document.ocr_job.status = OCRJob.Status.QUEUED
        document.ocr_job.error_code = ""
        document.ocr_job.error_message = ""
        document.ocr_job.save(update_fields=("status", "error_code", "error_message", "updated_at"))
        document.status = UploadedDocument.Status.QUEUED
        document.failure_reason = ""
        document.save(update_fields=("status", "failure_reason", "updated_at"))
        document.pages.update(processing_status=DocumentPage.ProcessingStatus.PENDING)
        if document.response_id:
            response = document.response
            invalidate_response(response)
            response.status = QuestionnaireResponse.Status.PROCESSING
            response.confirmed_at = None
            response.reviewed_by = None
            response.save(update_fields=("status", "confirmed_at", "reviewed_by", "updated_at"))
        process_document.delay(str(document.ocr_job.id))
        record_audit(actor=request.user, action="document.reprocessed", target=document, request=request)
        return Response(self.get_serializer(document).data, status=status.HTTP_202_ACCEPTED)


class ResponsePageViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = (WorkspacePermission,)
    http_method_names = ("get", "patch", "head", "options")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DocumentPage.objects.none()
        return (
            owned(DocumentPage.objects.all(), self.request.user, "response__batch__owner")
            .select_related("document", "response__batch")
            .prefetch_related("ocr_results")
        )

    def get_serializer_class(self):
        return ResponsePageUpdateSerializer if self.action == "partial_update" else ResponsePageSerializer

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        page = self.get_object()
        old_response_id = page.response_id
        serializer = self.get_serializer(page, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        page = serializer.save(
            classification_method=DocumentPage.ClassificationMethod.MANUAL,
            classification_confidence=1,
            validation_issues=[],
        )
        if page.document.page_count == 1 and page.document.response_id != page.response_id:
            page.document.response = page.response
            page.document.batch = page.response.batch
            page.document.save(update_fields=("response", "batch", "updated_at"))
        affected = {old_response_id, page.response_id}
        for response_id in affected:
            response = QuestionnaireResponse.objects.get(pk=response_id)
            invalidate_response(response, recheck_answers=True)
            refresh_response_validation(response_id)
            aggregate_response_answers(response_id, force=True)
            update_batch_status(response.batch_id)
        record_audit(actor=request.user, action="response_page.corrected", target=page, request=request)
        return Response(ResponsePageSerializer(page, context={"request": request}).data)
