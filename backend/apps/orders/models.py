from django.conf import settings
from django.db import models


class Order(models.Model):
    class Service(models.TextChoices):
        DIGITIZATION = 'DIGITIZATION', 'Questionnaire digitization'
        SYNTHETIC_DATA = 'SYNTHETIC_DATA', 'Synthetic TEST data'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        UPLOADING = 'UPLOADING', 'Uploading'
        AWAITING_PAYMENT = 'AWAITING_PAYMENT', 'Awaiting payment'
        PAYMENT_SUBMITTED = 'PAYMENT_SUBMITTED', 'Payment submitted'
        PAID = 'PAID', 'Paid'
        QUEUED = 'QUEUED', 'Queued'
        PROCESSING = 'PROCESSING', 'Processing'
        NEEDS_REVIEW = 'NEEDS_REVIEW', 'Needs attention'
        READY = 'READY', 'Ready'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class PaymentStatus(models.TextChoices):
        UNPAID = 'UNPAID', 'Unpaid'
        SUBMITTED = 'SUBMITTED', 'Submitted for verification'
        VERIFIED = 'VERIFIED', 'Verified'
        REJECTED = 'REJECTED', 'Rejected'

    reference = models.CharField(max_length=30, unique=True, null=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    title = models.CharField(max_length=255)
    service_type = models.CharField(max_length=20, choices=Service.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    respondent_count = models.PositiveIntegerField(default=0)
    pages_per_respondent = models.PositiveIntegerField(default=1)
    question_count = models.PositiveIntegerField(default=0)
    expected_page_count = models.PositiveIntegerField(default=0)
    synthetic_response_count = models.PositiveIntegerField(default=0)
    instructions = models.TextField(blank=True)
    google_form_url = models.CharField(max_length=500, blank=True)
    google_form_id = models.CharField(max_length=180, blank=True)
    amount_ngn = models.DecimalField(max_digits=12, decimal_places=2)
    pricing_snapshot = models.JSONField(default=dict)
    payment_method = models.CharField(max_length=24, default='BANK_TRANSFER', editable=False)
    payment_status = models.CharField(max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    payment_sender_name = models.CharField(max_length=180, blank=True)
    payment_reference = models.CharField(max_length=180, blank=True)
    payment_claimed_at = models.DateTimeField(null=True, blank=True)
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    payment_verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='verified_orders')
    payment_rejection_reason = models.TextField(blank=True)
    questionnaire = models.OneToOneField('questionnaires.Questionnaire', on_delete=models.PROTECT, related_name='order')
    response_batch = models.OneToOneField('questionnaires.ResponseBatch', on_delete=models.PROTECT, null=True, blank=True, related_name='order')
    bot_run = models.OneToOneField('botlab.BotRun', on_delete=models.PROTECT, null=True, blank=True, related_name='order')
    apps_script_job = models.OneToOneField('googleforms.AppsScriptJob', on_delete=models.PROTECT, null=True, blank=True, related_name='order')
    operator_notes = models.TextField(blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(condition=models.Q(amount_ngn__gt=0), name='order_positive_amount'),
            models.CheckConstraint(condition=(models.Q(service_type='DIGITIZATION', respondent_count__gt=0, synthetic_response_count=0, response_batch__isnull=False) | models.Q(service_type='SYNTHETIC_DATA', respondent_count=0, synthetic_response_count__gt=0, response_batch__isnull=True)), name='order_service_consistency'),
            models.CheckConstraint(condition=(models.Q(payment_status='VERIFIED', payment_verified_at__isnull=False, payment_verified_by__isnull=False) | (~models.Q(payment_status='VERIFIED') & models.Q(payment_verified_at__isnull=True, payment_verified_by__isnull=True))), name='order_payment_consistency'),
        ]

    def __str__(self):
        return f'{self.reference} — {self.title}'


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24, blank=True)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
