from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import decorators, mixins, status, viewsets
from rest_framework.response import Response as APIResponse

from apps.core.access import WorkspacePermission, owned
from apps.core.models import record_audit
from apps.documents.services.grouping import prepare_bulk_groups, update_batch_status

from .integrity import final_errors, invalidate_response
from .models import Answer, Questionnaire, Response, ResponseBatch
from .serializers import (
    AnswerSerializer,
    BulkGroupingSerializer,
    QuestionnaireSerializer,
    QuestionnaireVersionSerializer,
    ResponseBatchSerializer,
    ResponseCreateSerializer,
    ResponseSerializer,
    VersionCreateSerializer,
)


class QuestionnaireViewSet(viewsets.ModelViewSet):
    permission_classes = (WorkspacePermission,)
    serializer_class = QuestionnaireSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Questionnaire.objects.none()
        return owned(Questionnaire.objects.all(), self.request.user).prefetch_related(
            "versions__questions__options",
            "versions__template_pages",
        )

    def perform_create(self, serializer):
        questionnaire = serializer.save()
        record_audit(actor=self.request.user, action="questionnaire.created", target=questionnaire, request=self.request)

    def perform_destroy(self, instance):
        record_audit(actor=self.request.user, action="questionnaire.deleted", target=instance, request=self.request)
        instance.delete()

    @decorators.action(detail=True, methods=("post",), url_path="versions")
    def create_version(self, request, pk=None):
        questionnaire = self.get_object()
        serializer = VersionCreateSerializer(data=request.data, context={"questionnaire": questionnaire})
        serializer.is_valid(raise_exception=True)
        version = serializer.save()
        record_audit(actor=request.user, action="questionnaire.version_created", target=version, request=request)
        return APIResponse(QuestionnaireVersionSerializer(version).data, status=status.HTTP_201_CREATED)


class ResponseBatchViewSet(viewsets.ModelViewSet):
    permission_classes = (WorkspacePermission,)
    serializer_class = ResponseBatchSerializer
    http_method_names = ("get", "post", "delete", "head", "options")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ResponseBatch.objects.none()
        return (
            owned(ResponseBatch.objects.all(), self.request.user)
            .select_related("questionnaire_version__questionnaire")
            .annotate(
                response_count=Count("responses", distinct=True),
                physical_page_count=Count("responses__pages", distinct=True),
            )
        )

    def perform_create(self, serializer):
        batch = serializer.save()
        record_audit(actor=self.request.user, action="response_batch.created", target=batch, request=self.request)

    @decorators.action(detail=True, methods=("post",), url_path="prepare-bulk")
    def prepare_bulk(self, request, pk=None):
        batch = self.get_object()
        serializer = BulkGroupingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        responses, assignments = prepare_bulk_groups(request.user, batch, serializer.validated_data["file_count"])
        record_audit(
            actor=request.user,
            action="response_batch.bulk_group_prepared",
            target=batch,
            request=request,
            metadata={"response_count": len(responses), "file_count": len(assignments)},
        )
        return APIResponse(
            {
                "expected_page_count": batch.questionnaire_version.expected_page_count,
                "response_count": len(responses),
                "assignments": assignments,
            },
            status=status.HTTP_201_CREATED,
        )


class ResponseViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = (WorkspacePermission,)
    serializer_class = ResponseSerializer

    def get_serializer_class(self):
        return ResponseCreateSerializer if self.action == "create" else ResponseSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Response.objects.none()
        queryset = (
            owned(Response.objects.all(), self.request.user, "batch__owner")
            .select_related("batch__questionnaire_version__questionnaire")
            .prefetch_related(
                "answers__question__options",
                "documents",
                "pages__document",
                "pages__ocr_results",
            )
        )
        batch_id = self.request.query_params.get("batch")
        return queryset.filter(batch_id=batch_id) if batch_id else queryset

    def perform_create(self, serializer):
        response = serializer.save()
        record_audit(actor=self.request.user, action="response.created", target=response, request=self.request)

    @decorators.action(detail=True, methods=("post",))
    def confirm(self, request, pk=None):
        response = self.get_object()
        errors = final_errors(response, require_confirmation=False)
        if errors:
            return APIResponse({"detail": errors}, status=status.HTTP_409_CONFLICT)
        response.status = Response.Status.CONFIRMED
        response.confirmed_at = timezone.now()
        response.reviewed_by = request.user
        response.save(update_fields=["status", "confirmed_at", "reviewed_by", "updated_at"])
        update_batch_status(response.batch_id)
        record_audit(actor=request.user, action="response.confirmed", target=response, request=request)
        return APIResponse(self.get_serializer(response).data)


class AnswerViewSet(viewsets.GenericViewSet):
    permission_classes = (WorkspacePermission,)
    serializer_class = AnswerSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Answer.objects.none()
        return owned(Answer.objects.all(), self.request.user, "response__batch__owner").select_related("question", "response")

    @transaction.atomic
    def partial_update(self, request, pk=None):
        answer = self.get_object()
        serializer = self.get_serializer(answer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_response(answer.response)
        update_batch_status(answer.response.batch_id)
        record_audit(actor=request.user, action="answer.corrected", target=answer, request=request)
        return APIResponse(serializer.data)
