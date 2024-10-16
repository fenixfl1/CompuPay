from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms.models import model_to_dict
from rest_framework.request import Request
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from helpers.common import BaseProtectedViewSet
from helpers.exceptions import PayloadValidationError, viewException
from helpers.serializers import PaginationSerializer
from helpers.utils import advanced_query_filter, dict_key_to_lower, simple_query_filter
from tasks.models import TagXTasks, Tags, Task, TaskXusers
from tasks.serializers import TagSerializer, TaskSeriaizer
from users.models import ActivityLog


UserModel = get_user_model()


class TaskViewSet(BaseProtectedViewSet):
    """
    Tasks view set. This view set allows to manage the following actions:
    - `POST` Create a task
    - `PUT` Update a task (change state, priority, etc)
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

        assigned_users: list[str] = data.pop("assigned_users", [])
        tags = data.pop("tags", None)

        if not data:
            raise APIException("The body of the request is empty")

        if tags:
            tags = Tags.objects.filter(tag_id__in=tags)
            if not tags:
                raise APIException("The tag does not exist")

        data_s = data.copy()
        data_s["tags"] = None

        task = Task.create(request, **data)

        error_message = "Task created successfully"

        if tags:
            try:
                tags = Tags.objects.filter(tag_id__in=tags)
                task.add_tag_to_task(tags)
            finally:
                error_message = "But an error occurred while adding tags to the task"

        if assigned_users:
            try:
                assigned_users = UserModel.objects.filter(username__in=assigned_users)
                task.add_task_to_user(assigned_users)
            finally:
                error_message = "But an error occurred while adding users to the task"

        serializer = TaskSeriaizer(
            task, data=model_to_dict(task), context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        ActivityLog.register_activity(
            instance=task,
            user=request.user,
            action=1,
            message=f"@{request.user.username} creo la tarea '{task.name}'",
        )

        return Response(
            {"data": serializer.data, "message": f"Task created, {error_message}"}
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
            exclude=("created_by",),
            context={"request": request},
        ).is_valid(raise_exception=False)

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

        ActivityLog.register_activity(
            instance=task,
            user=request.user,
            action=2,
            message=f"@{request.user.username} ha hecho una acualización a la tarea '{task.name}'",
        )

        return Response(
            {"data": serializer.data, "message": "Task updated successfully"}
        )

    @viewException
    def update_task_state(self, request: Request):
        data = dict_key_to_lower(request.data)

        if not data:
            raise PayloadValidationError("The request body is empty.")

        task_id = data.get("task_id", None)
        if not task_id:
            raise PayloadValidationError("TASK_ID is required.")

        completed = data.get("completed", None)
        if completed is None:
            raise PayloadValidationError("COMPLETED is required.")

        task = Task.objects.filter(task_id=task_id)
        if task.exists() is False:
            raise APIException("Any task found with the given task_id.")

        task = task.first()

        completed_at = timezone.now() if completed is True else None
        Task.update(
            request=request,
            instance=task,
            completed=completed,
            completion_date=completed_at,
        )

        # Task.objects.filter(task_id=task_id).update(
        #     completed=completed, completion_date=completed_at
        # )

        text_action = "completada" if completed is True else "no completada"

        ActivityLog.register_activity(
            instance=task,
            user=request.user,
            action=2,
            message=f"La tarea '@{task.name}' se marco como {text_action} por @{request.user.username}",
        )

        return Response(
            {"message": f"La tarea '@{task.name}' se marco como {text_action}"}
        )

    @viewException
    def add_or_remove_user(self, request: Request):
        """
        This endpoint is used to add or remove users to tasks.
        `ALLOWED METHODS:` `POST`
        """

        data = dict_key_to_lower(request.data)
        if not data:
            raise PayloadValidationError("The request body is empty.")

        # Obtener la tarea
        try:
            task = Task.objects.get(task_id=data.get("task_id"))
        except Task.DoesNotExist:
            raise PayloadValidationError(
                "No task found with the given 'TASK_ID'"
            ) from Task.DoesNotExist

        # Obtener los usuarios asignados actualmente a la tarea
        current_users = set(
            TaskXusers.objects.filter(
                Q(task=task) & Q(state=TaskXusers.ACTIVE)
            ).values_list("user", flat=True)
        )

        # Obtener los nuevos usuarios que se envían en la solicitud
        new_usernames = data.get("assigned_users", [])
        new_users = set(UserModel.objects.filter(username__in=new_usernames))

        # Usuarios para inactivar (usuarios actuales que no están en la nueva lista)
        users_to_inactivate = current_users - new_users

        # Usuarios para agregar (nuevos usuarios que no están ya asignados a la tarea)
        users_to_add = new_users - current_users

        # Inactivar usuarios
        if users_to_inactivate:
            Task.remove_user_from_task(task, list(users_to_inactivate))

        # Agregar nuevos usuarios
        if users_to_add:
            TaskXusers.add_task_to_user(task, users_to_add)

        return Response({"message": "Users have been updated successfully."})

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

        ActivityLog.register_activity(
            instance=tag,
            user=request.user,
            action=1,
            message=f"@{request.user.username} una nueva etiqueta '{tag.name}'",
        )

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
