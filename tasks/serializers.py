from rest_framework import serializers
from tasks.models import Tags, Task
from helpers.serializers import BaseModelSerializer


class TaskSeriaizer(BaseModelSerializer):
    avatar = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    def get_tags(self, instance: Task | dict):
        if isinstance(instance, Task):
            return TagSerializer(instance.tags.all(), many=True).data
        return TagSerializer(data=instance.get("tags", []), many=True).data

    def get_avatar(self, instance: Task):
        assigned_user = instance.assigned_user
        return assigned_user.avatar or assigned_user.username[:2].upper()

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
