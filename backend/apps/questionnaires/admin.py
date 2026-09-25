from django.contrib import admin

from apps.core.admin import InspectOnlyAdmin

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


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 0


class TemplatePageInline(admin.TabularInline):
    model = TemplatePage
    extra = 0
    fields = ("page_number", "text_signature", "anchors")
    readonly_fields = ("text_signature", "anchors")


@admin.register(Question)
class QuestionAdmin(InspectOnlyAdmin):
    list_display = ("key", "text", "type", "position", "version")
    list_filter = ("type", "required")
    search_fields = ("text", "key")
    inlines = (QuestionOptionInline,)


@admin.register(Questionnaire)
class QuestionnaireAdmin(InspectOnlyAdmin):
    list_display = ("title", "owner", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "owner__email")


@admin.register(QuestionnaireVersion)
class QuestionnaireVersionAdmin(InspectOnlyAdmin):
    list_display = ("questionnaire", "version_number", "expected_page_count", "parse_status")
    inlines = (TemplatePageInline,)


@admin.register(ResponseBatch)
class ResponseBatchAdmin(InspectOnlyAdmin):
    list_display = ("name", "owner", "questionnaire_version", "status", "created_at")
    list_filter = ("status", "created_at")


@admin.register(Response)
class ResponseAdmin(InspectOnlyAdmin):
    list_display = ("respondent_reference", "sequence", "batch", "status", "expected_page_count", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("respondent_reference", "batch__name", "batch__owner__email")


admin.site.register(Answer, InspectOnlyAdmin)
