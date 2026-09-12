from django.urls import path

from .views import BatchCSVExportView, BatchXLSXExportView, ExportHistoryView

urlpatterns = [
    path("exports/", ExportHistoryView.as_view(), name="export-history"),
    path("exports/batches/<uuid:batch_id>/csv/", BatchCSVExportView.as_view(), name="batch-export-csv"),
    path("exports/batches/<uuid:batch_id>/xlsx/", BatchXLSXExportView.as_view(), name="batch-export-xlsx"),
]

