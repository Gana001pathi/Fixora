from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Booking, Notification


STATUS_NOTIFICATIONS = {
    "confirmed": (
        "confirmed",
        "Your booking has been confirmed.",
    ),
    "in progress": (
        "service_started",
        "Service for your booking has started.",
    ),
    "completed": (
        "service_completed",
        "Your service is complete.",
    ),
}


@receiver(pre_save, sender=Booking)
def remember_booking_state(sender, instance, **kwargs):
    previous = None
    if instance.pk:
        previous = sender.objects.filter(pk=instance.pk).values(
            "status", "technician_id"
        ).first()

    instance._previous_booking_status = previous["status"] if previous else None
    instance._previous_technician_id = previous["technician_id"] if previous else None


@receiver(post_save, sender=Booking)
def create_booking_notifications(sender, instance, created, update_fields=None, **kwargs):
    if created:
        return

    previous_status_value = instance._previous_booking_status or ""
    previous_technician_id = instance._previous_technician_id
    current_status_value = instance.status
    current_technician_id = instance.technician_id
    if update_fields is not None:
        update_fields = set(update_fields)
        if "status" not in update_fields:
            current_status_value = previous_status_value
        if not {"technician", "technician_id"}.intersection(update_fields):
            current_technician_id = previous_technician_id

    previous_status = previous_status_value.strip().casefold()
    current_status = current_status_value.strip().casefold()
    if previous_status != current_status and current_status in STATUS_NOTIFICATIONS:
        notification_type, message = STATUS_NOTIFICATIONS[current_status]
        Notification.objects.get_or_create(
            booking=instance,
            event_key=f"status:{current_status}",
            defaults={
                "notification_type": notification_type,
                "message": message,
            },
        )

    if current_technician_id and current_technician_id != previous_technician_id:
        Notification.objects.get_or_create(
            booking=instance,
            event_key=f"technician_assigned:{current_technician_id}",
            defaults={
                "notification_type": "technician_assigned",
                "message": "A technician has been assigned to your booking.",
            },
        )