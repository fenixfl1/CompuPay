# pylint: disable=unused-argument

import json
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.dispatch import receiver
from django.db.models.signals import post_save, m2m_changed

from tasks.models import Task, TaskXusers
from users.models import User


@receiver(post_save, sender=Task)
def create_task_group(sender, instance: Task, created: bool, **kwargs):
    channel_layer = get_channel_layer()
    group_name = f"task_{instance.task_id}"

    if created:
        for user in instance.users.all():
            async_to_sync(channel_layer.group_add)(group_name, user.username)
        async_to_sync(channel_layer.group_add)(group_name, instance.created_by.username)
    else:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "notification.message",
                "message": f"<a>{instance.updated_by}</a> ha hecho una actualización \
                en la tarea <a>f'{instance}'</a>",
            },
        )


@receiver(m2m_changed, sender=TaskXusers)
def update_task_group(
    sender,
    instance: TaskXusers,
    action: str,
    pk_set: set[int],
    **kwargs,
):
    channel_layer = get_channel_layer()
    group_name = f"task_{instance.task.task_id}"

    if action == "post_save":
        for user_id in pk_set:
            user = User.objects.get(pk=user_id)
            async_to_sync(channel_layer.group_add)(group_name, user.username)

        message = {
            "type": "task_notification",
            "message": f"@{instance.created_by} te asigno una nueva tarea '{instance}'",
        }

        async_to_sync(channel_layer.group_send)(
            group_name, {"type": "notification.message", "message": json.dumps(message)}
        )
