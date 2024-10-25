from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from core.settings import PATH_BASE
from .views import NotificationViwSet

BASE_NOTIFICATION_PATH = f"{PATH_BASE}ws/notifications"

get_notifications = NotificationViwSet.as_view({"get": "get_notifications"})

urlpatterns = [path(f"{BASE_NOTIFICATION_PATH}/<str:app_level>/", get_notifications)]
