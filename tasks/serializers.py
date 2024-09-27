from rest_framework import serializers
from django.db.models import Q
from django.contrib.auth import get_user_model

from tasks.models import Tags, Task, TaskXusers
from helpers.serializers import BaseModelSerializer, DynamicSerializer

User = get_user_model()


class TaskSeriaizer(BaseModelSerializer):
    tags = serializers.SerializerMethodField()
    assigned_users = serializers.SerializerMethodField()

    def get_assigned_users(self, instance: Task):
        task_users = TaskXusers.objects.filter(
            Q(task=instance) & Q(state=TaskXusers.ACTIVE)
        )
        users = User.objects.filter(
            username__in=task_users.values_list("user__username", flat=True)
        )

        return DynamicSerializer(
            model=User,
            fields=["username", "avatar", "full_name"],
            instance=users,
            many=True,
        ).data

    def get_tags(self, instance: Task | dict):
        if isinstance(instance, Task):
            return TagSerializer(instance.tags.all(), many=True).data
        return TagSerializer(data=instance.get("tags", []), many=True).data

    def __init__(
        self, instance=None, data=None, fields="__all__", exclude=None, **kwargs
    ):
        self.Meta.exclude = exclude
        self.Meta.fields = fields if exclude is None else None
        super().__init__(instance, data, **kwargs)

    class Meta:
        model = Task


class TagSerializer(BaseModelSerializer):
    class Meta:
        model = Tags
        fields = ("tag_id", "name", "description", "color")
