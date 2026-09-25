import re
from urllib.parse import urlparse

from rest_framework import serializers

from .generator import generate_apps_script
from .models import AppsScriptJob
from .services import resolve_script_source

FORM_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,180}$")


def normalize_form_id(value):
    value = value.strip()
    if value.startswith(("http://", "https://")):
        try:
            parsed = urlparse(value)
            port = parsed.port
        except ValueError as exc:
            raise serializers.ValidationError("The Google Form URL is malformed.") from exc
        if parsed.scheme != "https" or parsed.hostname != "docs.google.com" or parsed.username or parsed.password or port:
            raise serializers.ValidationError("Use an HTTPS Google Form edit URL at docs.google.com, or its edit Form ID.")
        match = re.fullmatch(r"/forms/d/([A-Za-z0-9_-]{20,180})(?:/edit)?/?", parsed.path)
        if not match:
            raise serializers.ValidationError("Use /forms/d/FORM_ID/edit. Public /d/e/ links and forms.gle short links are unsupported; ask the owner for the edit URL.")
        value = match.group(1)
    if not FORM_ID_PATTERN.fullmatch(value):
        raise serializers.ValidationError("The Google Form edit ID is invalid. Ownership is not verified by ScanToForms.")
    return value


class AppsScriptJobSerializer(serializers.ModelSerializer):
    source_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = AppsScriptJob
        fields = (
            "id",
            "source_type",
            "source_name",
            "form_id",
            "mappings",
            "script",
            "response_count",
            "data_classification",
            "download_url",
            "created_at",
        )
        read_only_fields = fields

    def get_source_name(self, obj) -> str:
        if obj.batch_id:
            return obj.batch.name
        return f"{obj.bot_run.questionnaire_version.questionnaire.title} — Bot Lab"

    def get_download_url(self, obj) -> str:
        return f"/api/v1/google-forms/scripts/{obj.id}/download/"


class AppsScriptPreviewQuestionSerializer(serializers.Serializer):
    key = serializers.CharField()
    text = serializers.CharField()
    type = serializers.CharField()
    suggested_google_item_title = serializers.CharField()


class AppsScriptPreviewSerializer(serializers.Serializer):
    title = serializers.CharField()
    source_type = serializers.ChoiceField(choices=AppsScriptJob.SourceType.choices)
    data_classification = serializers.CharField()
    response_count = serializers.IntegerField()
    questions = AppsScriptPreviewQuestionSerializer(many=True)


class AppsScriptCreateSerializer(serializers.Serializer):
    source_type = serializers.ChoiceField(choices=AppsScriptJob.SourceType.choices)
    source_id = serializers.UUIDField()
    form_id = serializers.CharField(max_length=500)
    mappings = serializers.DictField(child=serializers.CharField(allow_blank=True, max_length=300))

    def validate_form_id(self, value):
        return normalize_form_id(value)

    def validate(self, attrs):
        if attrs["source_type"] == AppsScriptJob.SourceType.BOT_RUN:
            raise serializers.ValidationError("Synthetic Google submission is blocked: classification is not preserved in the destination form. Deliver labelled CSV instead.")
        source = resolve_script_source(
            self.context["request"].user,
            attrs["source_type"],
            attrs["source_id"],
        )
        questions = list(source.version.questions.order_by("position"))
        question_keys = {question.key for question in questions}
        unknown = set(attrs["mappings"]) - question_keys
        if unknown:
            raise serializers.ValidationError({"mappings": f"Unknown questionnaire keys: {', '.join(sorted(unknown))}"})
        mappings = {question.key: attrs["mappings"].get(question.key, "").strip() for question in questions}
        selected_titles = [title.casefold() for title in mappings.values() if title]
        if not selected_titles:
            raise serializers.ValidationError({"mappings": "Map at least one questionnaire question."})
        if len(selected_titles) != len(set(selected_titles)):
            raise serializers.ValidationError({"mappings": "Each mapped Google Form item title must be unique."})
        attrs["source"] = source
        attrs["mappings"] = mappings
        return attrs

    def create(self, validated_data):
        source = validated_data.pop("source")
        validated_data.pop("source_id")
        job = AppsScriptJob(
            owner=self.context["request"].user,
            source_type=source.source_type,
            questionnaire_version=source.version,
            form_id=validated_data["form_id"],
            mappings=validated_data["mappings"],
            response_count=len(source.responses),
            data_classification=source.classification,
            batch=source.source if source.source_type == AppsScriptJob.SourceType.RESPONSE_BATCH else None,
            bot_run=source.source if source.source_type == AppsScriptJob.SourceType.BOT_RUN else None,
        )
        job.script = generate_apps_script(
            job_id=job.id,
            form_id=job.form_id,
            mappings=job.mappings,
            responses=source.responses,
            classification=source.classification,
        )
        job.save()
        return job
