from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms.models import model_to_dict
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from helpers.common import BaseProtectedViewSet
from helpers.exceptions import viewException
from helpers.serializers import PaginationSerializer
from helpers.utils import advanced_query_filter, dict_key_to_lower, simple_query_filter
from tasks.models import TagXTasks, Tags, Task
from tasks.serializers import TagSerializer, TaskSeriaizer


UserModel = get_user_model()


class TaskViewSet(BaseProtectedViewSet):
    """
    Tasks view set. This view set allows to manage the following actions:
    - `POST` Create a task
    - `PUT` Update a task (change state, status, priority, etc)
    - `POST` Get a list of tasks
    - `POST` Get a task
    - `POST` Get a list of tags
    - `POST` Create a tag
    - `PUT` Update a tag
    """

    pagination_class = PaginationSerializer

    @viewException
    def create_task(self, request):
        """
        Create a task
        """
        data: dict = dict_key_to_lower(request.data)

        assigned_user: str = data.get("assigned_user", None)
        tags = data.pop("tags", None)

        if not data:
            raise APIException("The body of the request is empty")

        if assigned_user:
            assigned_user = UserModel.objects.filter(username=assigned_user).first()
            if not assigned_user:
                raise APIException("The user does not exist")
            data["assigned_user"] = assigned_user

        if tags:
            tags = Tags.objects.filter(tag_id__in=tags)
            if not tags:
                raise APIException("The tag does not exist")

        data_s = data.copy()
        data_s["tags"] = None

        TaskSeriaizer(
            data=data,
            exclude=("created_by", "assigned_user"),
            context={"request": request},
        ).is_valid(raise_exception=True)

        task = Task.create(request, **data)

        for tag in tags:
            tag = Tags.objects.filter(tag_id=tag).first()
            tags_task = {"task": task, "tag": tag, "state": "A"}
            TagXTasks.create(request, **tags_task)

        serializer = TaskSeriaizer(
            task, data=model_to_dict(task), context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        return Response(
            {"data": serializer.data, "message": "Task created successfully"}
        )

    @viewException
    def update_task(self, request):
        """
        Update a task
        """
        data: dict = dict_key_to_lower(request.data)
        task_id: int = data.get("task_id", None)

        if not data:
            raise APIException("The body of the request is empty")

        if not task_id:
            raise APIException("The task_id is required")

        task = Task.objects.filter(task_id=task_id).first()
        if not task:
            raise APIException(f"Task with id {task_id} does not exist")

        TaskSeriaizer(
            task,
            data=data,
            exclude=("created_by", "assigned_user"),
            context={"request": request},
        ).is_valid(raise_exception=True)

        assigned_user = data.get("assigned_user", None)

        if assigned_user:
            assigned_user = UserModel.objects.filter(username=assigned_user).first()
            if not assigned_user:
                raise APIException("The user does not exist")
            data["assigned_user"] = assigned_user

        task = Task.update(request, task, **data)

        serializer = TaskSeriaizer(
            task, data=model_to_dict(task), context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        return Response(
            {"data": serializer.data, "message": "Task updated successfully"}
        )

    @viewException
    def get_tasks_list(self, request):
        """
        Get a list of tasks
        """
        condition: list[dict] = request.data.get("condition", None)

        if not condition:
            raise APIException("The condition is required")

        query, exclude = advanced_query_filter(condition)

        tasks = Task.objects.filter(query)
        if exclude:
            tasks = tasks.exclude(exclude)

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(tasks.distinct(), request)

        serializer = TaskSeriaizer(page, many=True, context={"request": request})

        return paginator.get_paginated_response(serializer.data)

    @viewException
    def get_task(self, request):
        """
        Get a task
        """
        condtion: dict = request.data.get("condition", None)

        if not condtion:
            raise APIException("The condition is required")
        if not isinstance(condtion, dict):
            raise APIException("The condition must be a dictionary")

        task = Task.objects.filter(simple_query_filter(condtion)).first()
        if not task:
            raise APIException("No task found with the given condition")

        serializer = TaskSeriaizer(
            task, data=model_to_dict(task), context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        return Response(
            {"data": serializer.data, "message": "Task retrieved successfully"}
        )

    @viewException
    def get_tags_list(self, request):
        """
        Get a list of tags
        """
        condition: list[dict] = request.data.get("condition", None)

        if not condition:
            raise APIException("The condition is required")

        query, exclude = advanced_query_filter(condition)

        tags = Tags.objects.filter(query)
        if exclude:
            tags = tags.exclude(exclude)

        tags = tags.distinct()

        serializer = TagSerializer(tags, many=True, context={"request": request})

        return Response({"data": serializer.data})

    @viewException
    def create_tag(self, request):
        """
        Create a tag
        """
        data: dict = dict_key_to_lower(request.data)

        if not data:
            raise APIException("The body of the request is empty")

        TagSerializer(data=data).is_valid(raise_exception=True)

        tag_count = Tags.objects.all().count() or 0
        data["tag_id"] = tag_count + 1
        tag = Tags.create(request, **data)

        serializer = TagSerializer(
            tag, data=model_to_dict(tag), context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        return Response(
            {"data": serializer.data, "message": "Tag created successfully"}
        )

    @viewException
    def update_tag(self, request):
        """
        Update a tag
        """
        data: dict = dict_key_to_lower(request.data)
        tag_id: int = data.get("tag_id", None)

        if not data:
            raise APIException("The body of the request is empty")

        if not tag_id:
            raise APIException("The tag_id is required")

        tag = Tags.objects.filter(tag_id=tag_id).first()
        if not tag:
            raise APIException(f"Tag with id {tag_id} does not exist")

        TagSerializer(tag, data=data).is_valid(raise_exception=True)
        tag = Tags.update(request, tag, **data)

        serializer = TagSerializer(
            tag, data=model_to_dict(tag), context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        return Response(
            {"data": serializer.data, "message": "Tag updated successfully"}
        )
