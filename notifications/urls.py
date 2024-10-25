from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from core.settings import PATH_BASE
from .views import NotificationViwSet

BASE_NOTIFICATION_PATH = f"{PATH_BASE}notifications"

get_notifications = NotificationViwSet.as_view({"post": "get_notifications"})
mark_as_read = NotificationViwSet.as_view({"put": "mark_as_read"})

urlpatterns = [
    path(f"{BASE_NOTIFICATION_PATH}/get_notifications", get_notifications),
    path(f"{BASE_NOTIFICATION_PATH}/mark_as_read", mark_as_read),
]

urlpatterns = format_suffix_patterns(urlpatterns)
