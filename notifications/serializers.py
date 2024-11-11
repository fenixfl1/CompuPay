from rest_framework import serializers

from helpers.serializers import BaseModelSerializer, DynamicSerializer
from helpers.utils import elapsed_time
from notifications.models import Notification
from users.models import User


class NotificationsSerializer(BaseModelSerializer):
    sender = serializers.SerializerMethodField()
    receiver = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    def get_created_at(self, instance: Notification):
        return elapsed_time(instance.created_at)

    def get_receiver(self, instance: Notification):
        serializer = DynamicSerializer(
            model=User,
            fields=["username", "avatar", "full_name"],
            instance=instance.receiver,
        )

        return serializer.data

    def get_sender(self, instance: Notification):
        serializer = DynamicSerializer(
            model=User,
            fields=["username", "avatar", "full_name"],
            instance=instance.sender,
        )

        return serializer.data

    class Meta:
        model = Notification
        fields = "__all__"
