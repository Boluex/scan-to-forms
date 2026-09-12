from rest_framework import serializers

from .models import ExportJob


class ExportJobSerializer(serializers.ModelSerializer):
    batch_name = serializers.CharField(source="batch.name", read_only=True)

    class Meta:
        model = ExportJob
        fields = ("id", "batch", "batch_name", "format", "status", "response_count", "error_message", "completed_at", "created_at")
        read_only_fields = fields

