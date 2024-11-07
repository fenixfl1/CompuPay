# pylint: disable=unused-argument

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import ActivityLog


@receiver(post_save, sender=ActivityLog)
def send_notification(sender, instance: ActivityLog, created, **kwargs):
    # channel_layer = get_channel_layer()
    # message = f"{instance}"

    # log = ActivityLog.objects.get(id=instance.pk)
    # key = log.related_object.pk

    # async_to_sync(channel_layer.group_send)(
    #     f"task_{key}",
    #     {
    #         "type": "notification.message",
    #         "message": message,
    #     },
    # )
    pass
