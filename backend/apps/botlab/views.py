import csv
from io import StringIO

from django.db import transaction
from django.http import HttpResponse
from rest_framework import decorators, status, viewsets
from rest_framework.response import Response

from apps.billing.services import reserve_bot_lab_run
from apps.core.models import record_audit

from .models import BotRun
from .serializers import BotRunSerializer
from .tasks import generate_synthetic_responses


class BotRunViewSet(viewsets.ModelViewSet):
    serializer_class = BotRunSerializer
    http_method_names = ("get", "post", "delete", "head", "options")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return BotRun.objects.none()
        return BotRun.objects.filter(owner=self.request.user).select_related(
            "questionnaire_version__questionnaire"
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            reserve_bot_lab_run(request.user)
            run = serializer.save()
            transaction.on_commit(lambda: generate_synthetic_responses.delay(str(run.id)))
        record_audit(actor=request.user, action="bot_lab.run_created", target=run, request=request)
        return Response(self.get_serializer(run).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=("get",), url_path="csv")
    def csv(self, request, pk=None):
        run = self.get_object()
        if run.status != BotRun.Status.COMPLETED:
            return Response({"detail": "This synthetic dataset is not ready."}, status=status.HTTP_409_CONFLICT)
        questions = list(run.questionnaire_version.questions.order_by("position"))
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["data_label", "synthetic_response_id", *[question.text for question in questions]])
        for response in run.responses.all():
            row = [response.data_label, str(response.id)]
            for question in questions:
                value = response.answers.get(question.key)
                row.append("; ".join(map(str, value)) if isinstance(value, list) else value)
            writer.writerow(row)
        payload = output.getvalue().encode("utf-8-sig")
        http_response = HttpResponse(payload, content_type="text/csv; charset=utf-8")
        http_response["Content-Disposition"] = f'attachment; filename="synthetic-{run.id}.csv"'
        record_audit(actor=request.user, action="bot_lab.csv", target=run, request=request)
        return http_response

