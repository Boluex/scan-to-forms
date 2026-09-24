from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.core.models import record_audit
from apps.documents.models import UploadedDocument
from apps.documents.services.grouping import create_document_pages
from apps.documents.validation import inspect_upload

from .models import Order
from .services import log_event, transition, upload_summary


@transaction.atomic
def save_upload(order, actor, data):
    order = Order.objects.select_for_update().get(pk=order.pk)
    existing = order.uploads.filter(upload_key=data['upload_key']).first()
    if existing:
        return existing  # Stable slot key makes interrupted upload retries idempotent.
    editable = order.status == 'UPLOADING' or (actor.is_staff and order.status in {'PAID', 'NEEDS_REVIEW', 'FAILED'})
    if not editable:
        raise ValidationError('Uploads are locked. Ask the operator to resolve a paid order.')
    upload = data['upload']
    inspection = inspect_upload(upload)
    kind = data['kind']
    if order.service_type == 'SYNTHETIC_DATA' and kind != 'TEMPLATE':
        raise ValidationError('Synthetic input is one blank questionnaire template, never respondent data.')
    if order.uploads.filter(document_type=kind, sha256=inspection['sha256']).exists():
        raise ValidationError('This exact file is already attached to the order.')
    response = None
    page_number = data.get('template_page_number')
    mode = data['grouping_mode']
    if kind == 'RESPONSE':
        sequence = data.get('respondent_sequence', 0)
        response = order.response_batch.responses.filter(sequence=sequence).first()
        if not response:
            raise ValidationError('Choose a respondent belonging to this order.')
        if inspection['page_count'] > 1 or inspection['content_type'] == 'application/pdf':
            if mode != 'PDF_PER_RESPONSE' or inspection['page_count'] != order.pages_per_respondent or response.pages.exists():
                raise ValidationError('Upload one complete PDF per respondent, with the stated page count and no existing pages.')
            page_number = None
        else:
            if not page_number or page_number > order.pages_per_respondent:
                raise ValidationError('Choose a valid page slot.')
            if response.pages.filter(assigned_template_page_number=page_number).exists():
                raise ValidationError('This page slot is occupied; remove the incorrect upload first.')
        if upload_summary(order)['uploaded_pages'] + inspection['page_count'] > order.expected_page_count:
            raise ValidationError('The upload exceeds the expected page count.')
    else:
        mode = 'TEMPLATE'
        current = sum(d.page_count for d in order.uploads.filter(document_type='TEMPLATE'))
        expected = order.expected_page_count if order.service_type == 'SYNTHETIC_DATA' else order.pages_per_respondent
        if current + inspection['page_count'] > expected:
            raise ValidationError('Too many pages for the one blank questionnaire template.')
    document = UploadedDocument.objects.create(owner=order.user, order=order, upload_key=data['upload_key'], questionnaire=order.questionnaire if kind == 'TEMPLATE' else None, batch=order.response_batch if kind == 'RESPONSE' else None, response=response, document_type=kind, file=upload, original_filename=upload.name[:255], size_bytes=upload.size, grouping_mode=mode, status='UPLOADED', **inspection)
    create_document_pages(document, template_page_number=page_number)
    # Deliberately no OCRJob, delay(), quota charge, or extraction before verification.
    log_event(order, actor, 'file_uploaded', metadata={'document_id': str(document.pk), 'kind': kind, 'pages': document.page_count})
    return document


@transaction.atomic
def delete_upload(order, document, actor):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if document.order_id != order.id or order.status not in {'UPLOADING', 'AWAITING_PAYMENT'}:
        raise ValidationError('Only this order’s unpaid uploads can be removed here. Paid corrections require an operator.')
    if order.status == 'AWAITING_PAYMENT':
        transition(order, 'UPLOADING', actor)
    name, storage = document.file.name, document.file.storage
    record_audit(actor=actor, action='order.file_removed', target=document)
    document.delete()
    transaction.on_commit(lambda: storage.delete(name))
