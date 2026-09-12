from django.contrib import admin

from .models import DocumentPage, ExtractionResult, OCRJob, OCRRegion, OCRResult, UploadedDocument


@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "owner", "document_type", "status", "page_count", "created_at")
    list_filter = ("document_type", "status", "created_at")
    search_fields = ("original_filename", "owner__email", "sha256")
    readonly_fields = ("sha256", "size_bytes", "content_type", "page_count")


@admin.register(OCRJob)
class OCRJobAdmin(admin.ModelAdmin):
    list_display = ("document", "status", "engine", "attempts", "processing_ms", "created_at")
    list_filter = ("status", "engine", "created_at")
    readonly_fields = ("started_at", "finished_at", "processing_ms", "error_code", "error_message")


@admin.register(DocumentPage)
class DocumentPageAdmin(admin.ModelAdmin):
    list_display = (
        "document",
        "response",
        "original_upload_order",
        "assigned_template_page_number",
        "classification_method",
        "processing_status",
    )
    list_filter = ("classification_method", "processing_status")


admin.site.register(OCRResult)
admin.site.register(OCRRegion)
admin.site.register(ExtractionResult)
