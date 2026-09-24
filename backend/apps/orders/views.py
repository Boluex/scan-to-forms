from django.conf import settings
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import decorators, permissions, status, throttling, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response as APIResponse

from apps.botlab.models import BotRun
from apps.botlab.views import synthetic_csv
from apps.documents.models import DocumentPage
from apps.exports.services import render_csv, render_xlsx
from apps.googleforms.serializers import AppsScriptCreateSerializer, normalize_form_id
from apps.questionnaires.integrity import final_errors, invalidate_response
from apps.questionnaires.serializers import QuestionnaireVersionSerializer

from . import services
from .models import Order
from .serializers import (
    OrderCreateSerializer,
    OrderSerializer,
    PaymentClaimSerializer,
    ReasonSerializer,
    SchemaSerializer,
    UploadSerializer,
)
from .uploads import delete_upload, save_upload


class OrderUploadThrottle(throttling.UserRateThrottle):
    scope = 'order_upload'


class OrderCreateThrottle(throttling.UserRateThrottle):
    scope = 'order_create'


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'reference'
    serializer_class = OrderSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        qs = Order.objects.select_related('user', 'questionnaire', 'response_batch', 'bot_run', 'apps_script_job')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        for field in ('status', 'service_type', 'payment_status'):
            if self.request.query_params.get(field):
                qs = qs.filter(**{field: self.request.query_params[field]})
        return qs

    def get_throttles(self):
        if self.action == 'uploads' and self.request.method == 'POST':
            return [OrderUploadThrottle()]
        if self.action == 'create':
            return [OrderCreateThrottle()]
        return super().get_throttles()

    def create(self, request):
        serializer = OrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return APIResponse(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny], authentication_classes=[])
    def configuration(self, request):
        return APIResponse({'digitization_rate_ngn': settings.DIGITIZATION_PRICE_PER_RESPONDENT_NGN, 'synthetic_rate_ngn': settings.SYNTHETIC_PRICE_PER_RESPONSE_NGN, 'payment_available': services.payment_available(), 'max_respondents': settings.MAX_ORDER_RESPONDENTS, 'max_pages': settings.MAX_ORDER_PAGES, 'max_synthetic_responses': settings.MAX_SYNTHETIC_RESPONSES, 'test_deployment': settings.TEST_DEPLOYMENT, 'processing_mode': settings.PROCESSING_MODE})

    def result(self, order):
        order.refresh_from_db()
        return APIResponse(self.get_serializer(order).data)

    @decorators.action(detail=True, methods=['get', 'post'])
    def uploads(self, request, reference=None):
        order = self.get_object()
        if request.method == 'POST':
            serializer = UploadSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            document = save_upload(order, request.user, serializer.validated_data)
            return APIResponse(self.upload_metadata(document), status=status.HTTP_201_CREATED)
        qs = order.uploads.select_related('response').order_by('created_at')
        page = self.paginate_queryset(qs)
        return self.get_paginated_response([self.upload_metadata(d) for d in page])

    @staticmethod
    def upload_metadata(document):
        return {'id': str(document.pk), 'upload_key': document.upload_key, 'filename': document.original_filename, 'page_count': document.page_count, 'kind': document.document_type, 'status': document.status, 'respondent_sequence': document.response.sequence if document.response_id else None}

    @decorators.action(detail=True, methods=['delete'], url_path='uploads/(?P<document_id>[^/.]+)')
    def remove_upload(self, request, reference=None, document_id=None):
        order = self.get_object()
        document = get_object_or_404(order.uploads, pk=document_id)
        delete_upload(order, document, request.user)
        return APIResponse(status=status.HTTP_204_NO_CONTENT)

    @decorators.action(detail=True, methods=['get'], url_path='uploads/(?P<document_id>[^/.]+)/file')
    def upload_file(self, request, reference=None, document_id=None):
        order = self.get_object()
        document = get_object_or_404(order.uploads, pk=document_id)
        return FileResponse(document.file.open('rb'), content_type=document.content_type, filename=document.original_filename)

    @decorators.action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, reference=None):
        return self.result(services.submit_for_payment(self.get_object(), request.user))

    @decorators.action(detail=True, methods=['post'], url_path='payment-claim')
    def payment_claim(self, request, reference=None):
        serializer = PaymentClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return self.result(services.claim_payment(self.get_object(), request.user, data['sender_name'], data['reference']))

    @decorators.action(detail=True, methods=['post'], url_path='verify-payment')
    def verify_payment(self, request, reference=None):
        return self.result(services.verify_payment(self.get_object(), request.user))

    @decorators.action(detail=True, methods=['post'], url_path='reject-payment')
    def reject_payment(self, request, reference=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.result(services.reject_payment(self.get_object(), request.user, serializer.validated_data['reason']))

    @decorators.action(detail=True, methods=['post'])
    def process(self, request, reference=None):
        return self.result(services.start_processing(self.get_object(), request.user))

    @decorators.action(detail=True, methods=['get', 'post'])
    def schema(self, request, reference=None):
        services.operator(request.user)
        order = self.get_object()
        if request.method == 'POST':
            serializer = SchemaSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            services.prepare_schema(order, request.user, serializer.validated_data['questions'])
        return APIResponse(QuestionnaireVersionSerializer(order.questionnaire.versions.first()).data)

    @decorators.action(detail=True, methods=['get'])
    def respondents(self, request, reference=None):
        order = self.get_object()
        if not order.response_batch_id:
            return APIResponse({'count': 0, 'next': None, 'previous': None, 'results': []})
        qs = order.response_batch.responses.prefetch_related('pages').order_by('sequence')
        page = self.paginate_queryset(qs)
        # Operational metadata only. Answers are never present in this customer endpoint.
        rows = [{'id': str(r.pk), 'sequence': r.sequence, 'reference': r.respondent_reference, 'status': r.status, 'expected_pages': r.expected_page_count, 'uploaded_pages': r.pages.count(), 'missing_pages': sorted(set(range(1, r.expected_page_count + 1)) - {p.assigned_template_page_number for p in r.pages.all()}), 'failed_pages': sum(p.processing_status == 'FAILED' for p in r.pages.all()), 'issues': r.validation_issues} for r in page]
        return self.get_paginated_response(rows)

    @decorators.action(detail=True, methods=['get'])
    def operator_detail(self, request, reference=None):
        services.operator(request.user)
        order = self.get_object()
        return APIResponse({'response_batch': str(order.response_batch_id) if order.response_batch_id else None, 'questionnaire': str(order.questionnaire_id), 'bot_run': str(order.bot_run_id) if order.bot_run_id else None, 'apps_script_job': str(order.apps_script_job_id) if order.apps_script_job_id else None, 'notes': order.operator_notes, 'readiness_errors': services.readiness_errors(order)[:30], 'events': list(order.events.values('action', 'from_status', 'to_status', 'note', 'created_at'))})

    @decorators.action(detail=True, methods=['post'])
    def note(self, request, reference=None):
        services.operator(request.user)
        order = self.get_object()
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order.operator_notes = serializer.validated_data['reason']
        order.save(update_fields=['operator_notes', 'updated_at'])
        services.log_event(order, request.user, 'note_added', note=order.operator_notes)
        return self.result(order)

    @decorators.action(detail=True, methods=['post'], url_path='manual-page-reviewed')
    def manual_page_reviewed(self, request, reference=None):
        services.operator(request.user)
        order = self.get_object()
        services.require_paid(order)
        if settings.PROCESSING_MODE != 'manual' or order.status != 'NEEDS_REVIEW':
            raise ValidationError('Manual page inspection is available only during manual transcription review.')
        page = get_object_or_404(DocumentPage, pk=request.data.get('page_id'), document__order=order, response__isnull=False)
        page.processing_status = 'COMPLETED'
        page.preprocessing = {'manual_inspection': True, 'ocr_executed': False, 'operator_id': request.user.pk}
        page.save(update_fields=['processing_status', 'preprocessing', 'updated_at'])
        invalidate_response(page.response)
        services.log_event(order, request.user, 'page_manually_inspected', metadata={'page_id': str(page.pk)})
        return APIResponse({'detail': 'Page inspection recorded. Answers still require manual transcription and approval.'})

    @decorators.action(detail=True, methods=['post'], url_path='generate-synthetic')
    def generate_synthetic(self, request, reference=None):
        return self.result(services.generate_synthetic(self.get_object(), request.user))

    @decorators.action(detail=True, methods=['post'], url_path='attach-bot-run')
    @transaction.atomic
    def attach_bot_run(self, request, reference=None):
        services.operator(request.user)
        order = Order.objects.select_for_update().get(pk=self.get_object().pk)
        services.require_paid(order)
        if order.service_type != 'SYNTHETIC_DATA' or order.status not in {'PROCESSING', 'NEEDS_REVIEW', 'FAILED'}:
            raise ValidationError('Only an active synthetic order can receive a dataset.')
        run = get_object_or_404(BotRun, pk=request.data.get('bot_run'), owner=order.user, questionnaire_version__questionnaire=order.questionnaire, status='COMPLETED')
        if run.responses.count() != order.synthetic_response_count or Order.objects.filter(bot_run=run).exclude(pk=order.pk).exists():
            raise ValidationError('Dataset count or order association is invalid.')
        order.bot_run = run
        order.save(update_fields=['bot_run', 'updated_at'])
        services.log_event(order, request.user, 'synthetic_result_attached', metadata={'classification': 'SYNTHETIC TEST DATA'})
        return self.result(order)

    @decorators.action(detail=True, methods=['get', 'post'], url_path='synthetic-responses')
    def synthetic_responses(self, request, reference=None):
        services.operator(request.user)
        order = self.get_object()
        services.require_paid(order)
        if not order.bot_run_id:
            raise ValidationError('Generate or attach a dataset first.')
        if request.method == 'POST':
            if order.status not in {'PROCESSING', 'NEEDS_REVIEW'}:
                raise ValidationError('Only datasets in preparation can be edited.')
            row = get_object_or_404(order.bot_run.responses, pk=request.data.get('id'))
            payload = request.data.get('answers')
            questions = list(order.bot_run.questionnaire_version.questions.all())
            if not isinstance(payload, dict) or set(payload) != {q.key for q in questions}:
                raise ValidationError('Supply exactly the questionnaire answer keys.')
            from apps.questionnaires.integrity import answer_error
            from apps.questionnaires.models import Answer
            for q in questions:
                value = payload[q.key]
                answer = Answer(question=q, value_json=value if isinstance(value, list | dict | int | float) else {}, value_text='' if value is None or isinstance(value, list | dict) else str(value))
                error = answer_error(answer)
                if error:
                    raise ValidationError({q.key: error})
            row.answers = payload
            row.save(update_fields=['answers', 'updated_at'])
            services.log_event(order, request.user, 'synthetic_row_corrected', metadata={'sequence': row.sequence, 'classification': 'SYNTHETIC TEST DATA'})
        page = self.paginate_queryset(order.bot_run.responses.all())
        return self.get_paginated_response([{'id': str(r.pk), 'sequence': r.sequence, 'answers': r.answers, 'data_label': r.data_label} for r in page])

    @decorators.action(detail=True, methods=['post'], url_path='prepare-script')
    @transaction.atomic
    def prepare_script(self, request, reference=None):
        services.operator(request.user)
        order = Order.objects.select_for_update().get(pk=self.get_object().pk)
        services.require_paid(order)
        if order.service_type != 'DIGITIZATION' or order.status not in {'PROCESSING', 'NEEDS_REVIEW'}:
            raise ValidationError('Only digitization orders under review support Apps Script delivery. Synthetic submission is blocked.')
        for response in order.response_batch.responses.all():
            errors = final_errors(response)
            if errors:
                raise ValidationError({response.respondent_reference: errors})
        form_id = normalize_form_id(request.data.get('form_id') or order.google_form_id)
        from types import SimpleNamespace
        serializer = AppsScriptCreateSerializer(data={'source_type': 'RESPONSE_BATCH', 'source_id': str(order.response_batch_id), 'form_id': form_id, 'mappings': request.data.get('mappings', {})}, context={'request': SimpleNamespace(user=order.user)})
        serializer.is_valid(raise_exception=True)
        order.apps_script_job = serializer.save()
        order.google_form_id = form_id
        order.save(update_fields=['apps_script_job', 'google_form_id', 'updated_at'])
        services.log_event(order, request.user, 'script_prepared')
        return self.result(order)

    @decorators.action(detail=True, methods=['post'])
    def ready(self, request, reference=None):
        return self.result(services.mark_ready(self.get_object(), request.user))

    @decorators.action(detail=True, methods=['post'])
    @transaction.atomic
    def complete(self, request, reference=None):
        order = Order.objects.select_for_update().get(pk=self.get_object().pk)
        services.require_delivery(order)
        order.completed_at = timezone.now()
        services.transition(order, 'COMPLETED', request.user, note='Delivery acknowledged; Google execution is not remotely verified.')
        return self.result(order)

    @decorators.action(detail=True, methods=['get'])
    def script(self, request, reference=None):
        order = self.get_object()
        services.require_delivery(order)
        if order.service_type != 'DIGITIZATION':
            raise ValidationError('Synthetic Google submission is not enabled.')
        services.log_event(order, request.user, 'script_retrieved')
        if request.query_params.get('download') == '1':
            response = HttpResponse(order.apps_script_job.script, content_type='text/javascript; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{order.reference}.gs"'
            return response
        return APIResponse({'script': order.apps_script_job.script, 'classification': order.apps_script_job.data_classification})

    @decorators.action(detail=True, methods=['get'])
    def export(self, request, reference=None):
        order = self.get_object()
        services.require_delivery(order)
        fmt = request.query_params.get('format', 'csv')
        if order.service_type == 'SYNTHETIC_DATA':
            if fmt != 'csv':
                raise ValidationError('Synthetic TEST datasets are delivered as labelled CSV.')
            payload = synthetic_csv(order.bot_run)
        elif fmt in {'csv', 'xlsx'}:
            payload, _ = (render_csv if fmt == 'csv' else render_xlsx)(order.response_batch)
        else:
            raise ValidationError('Choose csv or xlsx.')
        services.log_event(order, request.user, 'result_exported', metadata={'format': fmt, 'service': order.service_type})
        response = HttpResponse(payload, content_type='text/csv; charset=utf-8' if fmt == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{order.reference}-{order.service_type.lower()}.{fmt}"'
        return response
