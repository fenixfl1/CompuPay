from django.shortcuts import render
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet


from helpers.common import BaseProtectedViewSet

# Create your views here.


class NotificationViwSet(ViewSet):

    def get_notifications(self, request: Request, app_level):
        return Response({"message": f"Hello, Word. {app_level}"})
