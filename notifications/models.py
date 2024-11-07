# pylint: disable=unsubscriptable-object

from django.db import models
from django.db.models import Q

from helpers.models import BaseModels


class Notification(models.Model):
    sender = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        to_field="username",
        related_name="%(class)s_sender",
        db_column="sender",
    )
    receiver = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        to_field="username",
        related_name="%(class)s_receiver",
        db_column="receiver",
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    state = models.CharField(default="A", choices=BaseModels.STATE_CHOICES)

    class Meta:
        db_table = "NOTIFICATION"
        ordering = ["-created_at"]
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return f"Notificación para {self.receiver.username} - {self.message[:20]}"

    @classmethod
    def mark_as_read(cls, username: str):
        notifications = cls.objects.filter(
            Q(receiver__username=username) & Q(is_read=False)
        )

        for notification in notifications:
            notification.is_read = True

        cls.objects.bulk_update(notifications, ["is_read"])
