from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from rest_framework.exceptions import APIException


from helpers.common import BaseProtectedViewSet
from helpers.exceptions import PayloadValidationError, viewException
from helpers.serializers import PaginationSerializer
from helpers.utils import advanced_query_filter, dict_key_to_lower
from notifications.models import Notification
from notifications.serializers import NotificationsSerializer

User = get_user_model()


class NotificationViwSet(BaseProtectedViewSet):

    @viewException
    def get_notifications(self, request: Request):

        conditions = request.data.get("condition")
        if not conditions:
            raise PayloadValidationError("'CONDITION' is required")

        condition, exclude = advanced_query_filter(conditions)

        notification = Notification.objects.filter(condition)

        for ex in exclude:
            notification = notification.exclude(**ex)

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(notification, request)

        serializer = NotificationsSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)

    @viewException
    def mark_as_read(self, request: Request):
        data = dict_key_to_lower(request.data.get("condition", None))

        if not data:
            raise PayloadValidationError("condition is required.")

        username = data.get("username", None)
        if not username:
            raise PayloadValidationError("username is missing in the condition body")

        if User.objects.filter(username=username).exists() is False:
            raise PayloadValidationError(f"The user '{username}' does not exists.")

        Notification.mark_as_read(username)

        return Response({"message": ""})
