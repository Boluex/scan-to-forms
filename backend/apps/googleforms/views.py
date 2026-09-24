from django.http import HttpResponse
from rest_framework import decorators, generics, status, viewsets
from rest_framework.response import Response

from apps.billing.services import require_feature
from apps.core.access import WorkspacePermission, owned
from apps.core.models import record_audit

from .models import AppsScriptJob
from .serializers import (
    AppsScriptCreateSerializer,
    AppsScriptJobSerializer,
    AppsScriptPreviewSerializer,
)
from .services import resolve_script_source, source_preview


class AppsScriptPreviewView(generics.GenericAPIView):
    permission_classes = (WorkspacePermission,)
    serializer_class = AppsScriptPreviewSerializer

    def get(self, request):
        require_feature(request.user, "has_google_forms")
        source_type = request.query_params.get("source_type", "")
        source_id = request.query_params.get("source_id", "")
        source = resolve_script_source(request.user, source_type, source_id)
        return Response(source_preview(source))


class AppsScriptJobViewSet(viewsets.ModelViewSet):
    permission_classes = (WorkspacePermission,)
    http_method_names = ("get", "post", "delete", "head", "options")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AppsScriptJob.objects.none()
        return owned(AppsScriptJob.objects.all(), self.request.user).select_related(
            "batch",
            "bot_run__questionnaire_version__questionnaire",
        )

    def get_serializer_class(self):
        return AppsScriptCreateSerializer if self.action == "create" else AppsScriptJobSerializer

    def create(self, request, *args, **kwargs):
        require_feature(request.user, "has_google_forms")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        record_audit(actor=request.user, action="google_forms.script_generated", target=job, request=request)
        return Response(AppsScriptJobSerializer(job).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=("get",))
    def download(self, request, pk=None):
        job = self.get_object()
        response = HttpResponse(job.script, content_type="text/javascript; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="scan-to-forms-{job.id}.gs"'
        record_audit(actor=request.user, action="google_forms.script_downloaded", target=job, request=request)
        return response
