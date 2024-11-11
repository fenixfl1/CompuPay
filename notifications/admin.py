from django.contrib import admin

from helpers.admin import BaseModelAdmin
from notifications.models import Notification


class NotificationAdmin(BaseModelAdmin):
    list_display = ("id", "sender", "receiver", "message", "is_read")
    list_filter = ("state", "is_read")


admin.site.register(Notification, NotificationAdmin)
