import json
import socketio
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import ActivityLog

sio = socketio.AsyncClient()


@receiver(post_save, sender=ActivityLog)
def send_notification(sender, instance, created, **kwargs):
    created
    sender
    channel_layer = get_channel_layer()
    message = f"Nuevo registro creado: {instance}"

    channel_layer.send(
        "channel_name", {"type": "notification.message", "message": message}
    )

    async_to_sync(channel_layer.group_send)(
        "notification",
        {
            "type": "notification.message",
            "message": message,
        },
    )
