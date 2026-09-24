from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics

from apps.billing.services import require_feature
from apps.core.access import WorkspacePermission, owned
from apps.core.models import record_audit
from apps.notifications.models import Notification
from apps.questionnaires.models import ResponseBatch

from .models import ExportJob
from .serializers import ExportJobSerializer
from .services import render_csv, render_xlsx


class ExportHistoryView(generics.ListAPIView):
    permission_classes = (WorkspacePermission,)
    serializer_class = ExportJobSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ExportJob.objects.none()
        return owned(ExportJob.objects.all(), self.request.user).select_related("batch")


class BatchExportView(generics.GenericAPIView):
    permission_classes = (WorkspacePermission,)
    format_name = None
    serializer_class = ExportJobSerializer

    def get(self, request, batch_id):
        if self.format_name == ExportJob.Format.XLSX:
            require_feature(request.user, "has_xlsx")
        batch = get_object_or_404(
            owned(ResponseBatch.objects.select_related("questionnaire_version__questionnaire"), request.user),
            pk=batch_id,
        )
        export = ExportJob.objects.create(owner=request.user, batch=batch, format=self.format_name)
        try:
            if self.format_name == ExportJob.Format.CSV:
                payload, count = render_csv(batch)
                content_type = "text/csv; charset=utf-8"
                extension = "csv"
            else:
                payload, count = render_xlsx(batch)
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                extension = "xlsx"
            export.status = ExportJob.Status.COMPLETED
            export.response_count = count
            export.completed_at = timezone.now()
            export.save(update_fields=("status", "response_count", "completed_at", "updated_at"))
            Notification.objects.create(
                user=request.user,
                kind=Notification.Kind.EXPORT_READY,
                title="Export ready",
                message=f"{batch.name} was exported as {extension.upper()}.",
                data={"batch_id": str(batch.id), "export_id": str(export.id)},
            )
            record_audit(actor=request.user, action=f"export.{extension}", target=export, request=request)
            response = HttpResponse(payload, content_type=content_type)
            safe_name = "".join(character if character.isalnum() or character in "-_" else "_" for character in batch.name)
            response["Content-Disposition"] = f'attachment; filename="{safe_name or "responses"}.{extension}"'
            return response
        except Exception as exc:
            export.status = ExportJob.Status.FAILED
            export.error_message = str(exc)[:4000]
            export.save(update_fields=("status", "error_message", "updated_at"))
            raise


class BatchCSVExportView(BatchExportView):
    permission_classes = (WorkspacePermission,)
    format_name = ExportJob.Format.CSV


class BatchXLSXExportView(BatchExportView):
    permission_classes = (WorkspacePermission,)
    format_name = ExportJob.Format.XLSX
