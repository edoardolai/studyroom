import logging

from celery import shared_task
from django.db import OperationalError
from kombu.exceptions import OperationalError as BrokerError

from .models import CourseMaterial, Notification

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(OperationalError,), retry_kwargs={"max_retries": 3, "countdown": 2})
def notify_material(material_id):
    material = CourseMaterial.objects.select_related("course").filter(pk=material_id).first()
    if material is None:
        return
    enrolments = material.course.enrolments.filter(
        is_blocked=False, student__is_active=True, student__role="student",
        enrolled_at__lte=material.uploaded_at,
    )
    for student_id in enrolments.values_list("student_id", flat=True):
        # A repeated task should not give the student the same notice twice.
        Notification.objects.get_or_create(
            recipient_id=student_id, material=material,
            defaults={"course": material.course, "message": f"New material in {material.course.title}: {material.title}."},
        )


def queue_material_notification(material_id):
    try:
        notify_material.delay(material_id)
    except BrokerError:
        logger.warning("Notification queue unavailable; creating material notices directly.")
        notify_material.run(material_id)
