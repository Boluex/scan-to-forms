from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "kind", "title", "message", "data", "read_at", "created_at")
        read_only_fields = fields


class PushTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=2048, min_length=20, trim_whitespace=False)
    label = serializers.CharField(max_length=120, required=False, allow_blank=True)
