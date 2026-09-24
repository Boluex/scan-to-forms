from django.conf import settings
from rest_framework import serializers

from apps.googleforms.serializers import normalize_form_id
from apps.questionnaires.serializers import QuestionSerializer

from .models import Order
from .services import bank_details, create_order, payment_available, upload_summary


class OrderCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    service_type = serializers.ChoiceField(choices=Order.Service.choices)
    respondent_count = serializers.IntegerField(min_value=0, default=0)
    pages_per_respondent = serializers.IntegerField(min_value=1, max_value=100, default=1)
    question_count = serializers.IntegerField(min_value=1, max_value=500)
    expected_page_count = serializers.IntegerField(min_value=1, max_value=100, required=False)
    synthetic_response_count = serializers.IntegerField(min_value=0, default=0)
    instructions = serializers.CharField(max_length=10000, allow_blank=True, default='')
    google_form_url = serializers.CharField(max_length=500, allow_blank=True, default='')
    questions = serializers.ListField(child=serializers.CharField(max_length=2000), max_length=500, default=list)

    def validate(self, attrs):
        if attrs['service_type'] == 'DIGITIZATION':
            if not 1 <= attrs['respondent_count'] <= settings.MAX_ORDER_RESPONDENTS or attrs['synthetic_response_count']:
                raise serializers.ValidationError('Choose a supported respondent count; digitization has no synthetic responses.')
            attrs['expected_page_count'] = attrs['respondent_count'] * attrs['pages_per_respondent']
            if attrs['expected_page_count'] > settings.MAX_ORDER_PAGES:
                raise serializers.ValidationError('This order exceeds the configured page limit.')
        else:
            if attrs['respondent_count'] or not 1 <= attrs['synthetic_response_count'] <= settings.MAX_SYNTHETIC_RESPONSES:
                raise serializers.ValidationError('Synthetic orders describe one template and a synthetic response count, not human respondents.')
            if not attrs.get('expected_page_count'):
                raise serializers.ValidationError('Enter the number of pages in the one blank questionnaire.')
            attrs['pages_per_respondent'] = 1
        if attrs['questions'] and len(attrs['questions']) != attrs['question_count']:
            raise serializers.ValidationError('Enter exactly the stated number of questions, or leave schema preparation to the operator.')
        attrs['google_form_id'] = normalize_form_id(attrs['google_form_url']) if attrs['google_form_url'] else ''
        return attrs

    def create(self, validated_data):
        return create_order(self.context['request'].user, validated_data)


class OrderSerializer(serializers.ModelSerializer):
    uploads_summary = serializers.SerializerMethodField()
    bank = serializers.SerializerMethodField()
    payment_available = serializers.SerializerMethodField()
    result_available = serializers.SerializerMethodField()
    classification = serializers.SerializerMethodField()
    processing_mode = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ('reference', 'title', 'service_type', 'status', 'respondent_count', 'pages_per_respondent', 'question_count', 'expected_page_count', 'synthetic_response_count', 'instructions', 'google_form_url', 'google_form_id', 'amount_ngn', 'pricing_snapshot', 'payment_method', 'payment_status', 'payment_sender_name', 'payment_reference', 'payment_claimed_at', 'payment_verified_at', 'payment_rejection_reason', 'created_at', 'processing_started_at', 'ready_at', 'completed_at', 'uploads_summary', 'bank', 'payment_available', 'result_available', 'classification', 'processing_mode')
        read_only_fields = fields

    def get_uploads_summary(self, obj):
        return upload_summary(obj)

    def get_bank(self, obj):
        return bank_details() if obj.status in {'AWAITING_PAYMENT', 'PAYMENT_SUBMITTED'} else None

    def get_payment_available(self, obj):
        return payment_available()

    def get_result_available(self, obj):
        return obj.payment_status == 'VERIFIED' and obj.status in {'READY', 'COMPLETED'}

    def get_classification(self, obj):
        return 'SYNTHETIC TEST DATA — NOT HUMAN RESEARCH RESPONSES' if obj.service_type == 'SYNTHETIC_DATA' else 'DIGITIZED HUMAN RESPONSES'

    def get_processing_mode(self, obj):
        return settings.PROCESSING_MODE


class UploadSerializer(serializers.Serializer):
    upload = serializers.FileField()
    upload_key = serializers.CharField(max_length=100)
    kind = serializers.ChoiceField(choices=['RESPONSE', 'TEMPLATE'])
    respondent_sequence = serializers.IntegerField(min_value=1, required=False)
    template_page_number = serializers.IntegerField(min_value=1, max_value=100, required=False)
    grouping_mode = serializers.ChoiceField(choices=['BULK_ORDERED', 'MANUAL_RESPONSE', 'PDF_PER_RESPONSE'], default='BULK_ORDERED')


class PaymentClaimSerializer(serializers.Serializer):
    sender_name = serializers.CharField(max_length=180, allow_blank=True, default='')
    reference = serializers.CharField(max_length=180, allow_blank=True, default='')


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=4000)


class SchemaSerializer(serializers.Serializer):
    questions = QuestionSerializer(many=True)

    def validate_questions(self, value):
        if len({q['key'] for q in value}) != len(value) or len({q['position'] for q in value}) != len(value):
            raise serializers.ValidationError('Question keys and positions must be unique.')
        for question in value:
            options = question.get('options', [])
            if len({o['key'] for o in options}) != len(options) or len({o['position'] for o in options}) != len(options):
                raise serializers.ValidationError('Option keys and positions must be unique.')
        return value
