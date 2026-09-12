from django.db.models import Count
from django.utils import timezone
from rest_framework import decorators, mixins, status, viewsets
from rest_framework.response import Response as APIResponse

from apps.core.models import record_audit
from apps.documents.services.grouping import prepare_bulk_groups, update_batch_status

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
    serializer_class = QuestionnaireSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Questionnaire.objects.none()
        return Questionnaire.objects.filter(owner=self.request.user).prefetch_related(
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
    serializer_class = ResponseBatchSerializer
    http_method_names = ("get", "post", "delete", "head", "options")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ResponseBatch.objects.none()
        return (
            ResponseBatch.objects.filter(owner=self.request.user)
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
    serializer_class = ResponseSerializer

    def get_serializer_class(self):
        return ResponseCreateSerializer if self.action == "create" else ResponseSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Response.objects.none()
        queryset = (
            Response.objects.filter(batch__owner=self.request.user)
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
        blocking_page_issues = [
            issue
            for page in response.pages.all()
            for issue in page.validation_issues
        ]
        blocking_response_issues = [
            issue for issue in response.validation_issues if issue.get("severity", "ERROR") == "ERROR"
        ]
        if response.status in {
            Response.Status.UPLOADING,
            Response.Status.INCOMPLETE,
            Response.Status.READY_FOR_PROCESSING,
            Response.Status.PROCESSING,
            Response.Status.FAILED,
        } or blocking_page_issues or blocking_response_issues:
            return APIResponse(
                {
                    "detail": "Resolve response-page grouping and processing issues before confirming.",
                    "response_issues": response.validation_issues,
                    "page_issues": blocking_page_issues,
                },
                status=status.HTTP_409_CONFLICT,
            )
        unresolved = response.answers.filter(review_status=Answer.ReviewStatus.NEEDS_REVIEW).count()
        if unresolved:
            return APIResponse(
                {"detail": f"Review {unresolved} low-confidence answer(s) before confirming."},
                status=status.HTTP_409_CONFLICT,
            )
        required_missing = [
            answer.question.text
            for answer in response.answers.all()
            if answer.question.required and not answer.value_text.strip() and answer.value_json in ({}, [], None)
        ]
        if required_missing:
            return APIResponse(
                {"detail": {"message": "Required answers are missing.", "questions": required_missing}},
                status=status.HTTP_409_CONFLICT,
            )
        response.status = Response.Status.CONFIRMED
        response.confirmed_at = timezone.now()
        response.reviewed_by = request.user
        response.save(update_fields=["status", "confirmed_at", "reviewed_by", "updated_at"])
        update_batch_status(response.batch_id)
        record_audit(actor=request.user, action="response.confirmed", target=response, request=request)
        return APIResponse(self.get_serializer(response).data)


class AnswerViewSet(viewsets.GenericViewSet):
    serializer_class = AnswerSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Answer.objects.none()
        return Answer.objects.filter(response__batch__owner=self.request.user).select_related("question", "response")

    def partial_update(self, request, pk=None):
        answer = self.get_object()
        serializer = self.get_serializer(answer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if answer.response.status == Response.Status.PROCESSING:
            answer.response.status = Response.Status.NEEDS_REVIEW
            answer.response.save(update_fields=["status", "updated_at"])
        record_audit(actor=request.user, action="answer.corrected", target=answer, request=request)
        return APIResponse(serializer.data)
