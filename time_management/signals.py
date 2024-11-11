# pylint: disable=unused-argument

from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import ActivityLog
from time_management.models import Leaves, Overtime


@receiver(post_save, sender=Leaves)
def leave_signal(sender, instance: Leaves, created, **kwargs):
    action = 1 if created else 2
    ActivityLog.register_activity(
        instance=instance,
        user=instance.created_by,
        action=action,
        message=f"{instance.created_by} registro {instance.concept.name} \
            para el usuario @{instance.employee.username}"
    )


@receiver(post_save, sender=Overtime)
def overtime_signal(sender, instance: Overtime, created, **kwargs):
    action = 1 if created else 2
    ActivityLog.register_activity(
        instance=instance,
        user=instance.created_by,
        action=action,
        message=f"{instance.created_by} registro\
            horas extras a @{instance.employee.username}"
    )
