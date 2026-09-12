import secrets

from rest_framework import serializers

from apps.billing.models import Plan
from apps.billing.services import entitlements_for

from .models import BotRun


class BotRunSerializer(serializers.ModelSerializer):
    questionnaire_title = serializers.CharField(source="questionnaire_version.questionnaire.title", read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = BotRun
        fields = (
            "id",
            "questionnaire_version",
            "questionnaire_title",
            "requested_responses",
            "generated_responses",
            "status",
            "error_message",
            "download_url",
            "created_at",
        )
        read_only_fields = (
            "id",
            "questionnaire_title",
            "generated_responses",
            "status",
            "error_message",
            "download_url",
            "created_at",
        )

    def validate_questionnaire_version(self, value):
        if value.questionnaire.owner_id != self.context["request"].user.id:
            raise serializers.ValidationError("Questionnaire version not found.")
        return value

    def validate_requested_responses(self, value):
        plan = entitlements_for(self.context["request"].user).plan
        limits = {
            Plan.Code.STUDENT: 100,
            Plan.Code.RESEARCHER: 500,
            Plan.Code.ORGANIZATION: 1000,
        }
        maximum = limits.get(plan.code, 0)
        if maximum == 0:
            raise serializers.ValidationError("Bot Lab is available on a Pro plan.")
        if value < 1 or value > maximum:
            raise serializers.ValidationError(f"Your plan allows 1 to {maximum} synthetic responses per Bot Lab run.")
        return value

    def create(self, validated_data):
        return BotRun.objects.create(
            owner=self.context["request"].user,
            seed=secrets.randbits(63),
            **validated_data,
        )

    def get_download_url(self, obj) -> str | None:
        if obj.status != BotRun.Status.COMPLETED:
            return None
        return f"/api/v1/bot-lab/runs/{obj.id}/csv/"
