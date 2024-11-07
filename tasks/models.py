from django.db import models
from django.utils.html import format_html
from django.utils.safestring import SafeText

from rest_framework.exceptions import APIException

from helpers.models import STATE_CHOICES, BaseModels
from users.models import User


class Task(BaseModels):
    STATE_CHOICES = STATE_CHOICES
    PRIORITY_CHOICES = (
        ("H", "High"),
        ("M", "Medium"),
        ("L", "Low"),
    )

    task_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(
        max_length=1, null=True, blank=True, choices=PRIORITY_CHOICES
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField(
        "Tags",
        through="TagXTasks",
        through_fields=("task", "tag"),
        related_name="%(class)s_tags",
    )
    users = models.ManyToManyField(
        User,
        through="TaskXusers",
        through_fields=("task", "user"),
        related_name="%(class)s_users",
    )

    def __str__(self):
        return f"{self.pk} - {self.name}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def add_task_to_user(self, users: list[User]) -> None:
        task_users = []
        count = TaskXusers.objects.all().count()
        for user in users:
            count += 1
            task_users.append(
                TaskXusers(
                    id=count,
                    task=self,
                    user=user,
                    created_by=self.created_by,
                    state=TaskXusers.ACTIVE,
                )
            )
        return TaskXusers.objects.bulk_create(task_users)

    def remove_user_from_task(self, users: list[User]) -> None:
        for user in users:
            # update the state of the user to inactive
            task_user = TaskXusers.objects.filter(task=self, user=user).first()
            if task_user:
                task_user.state = TaskXusers.INACTIVE
                task_user.save()

    def add_tag_to_task(self, tags: list["Tags"]) -> None:
        task_tags = []
        count = TagXTasks.objects.all().count()
        for tag in tags:
            count += 1
            task_tags.append(
                TagXTasks(id=count, task=self, tag=tag, created_by=self.created_by)
            )
        return TagXTasks.objects.bulk_create(task_tags)

    def remove_tag_from_task(self, tags: list["Tags"]) -> None:
        for tag in tags:
            # update the state of the tag to inactive
            tag_task = TagXTasks.objects.filter(task=self, tag=tag).first()
            if tag_task:
                tag_task.state = TagXTasks.INACTIVE
                tag_task.save()

    def get_assigned_users(self):
        # pylint: disable=no-member
        return ", ".join([user.username for user in self.users.all()])

    get_assigned_users.short_description = "Assigned users"

    class Meta:
        db_table = "TASKS"
        verbose_name = "Task"
        verbose_name_plural = "Tasks"
        ordering = ["-task_id"]


class TaskXusers(BaseModels):
    """
    This model represents the relationship between tasks and users.\n
    `TABLE` TASKS_X_USERS
    """

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="%(class)s_task",
        db_column="task_id",
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="%(class)s_user",
        db_column="username",
    )

    def __str__(self):
        return f"{self.pk} - {self.task} - {self.user}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.task!r} - {self.user!r})"

    @classmethod
    def add_task_to_user(cls, task: Task, users: list[User]) -> None:
        task_users = []
        task_users_to_update = []

        count = TaskXusers.objects.all().count()
        for user in users:
            count += 1
            # Verifica si el usuario ya está asignado a la tarea
            task_user = TaskXusers.objects.filter(task=task, user=user).first()

            if task_user:
                # Si está asignado y el estado es INACTIVE, actualiza a ACTIVE
                if task_user.state == TaskXusers.INACTIVE:
                    task_user.state = TaskXusers.ACTIVE
                    task_users_to_update.append(task_user)
            else:
                # Si no está asignado, crea una nueva relación
                task_users.append(
                    TaskXusers(
                        id=count,
                        task=task,
                        user=user,
                        created_by=task.created_by,
                        state=TaskXusers.ACTIVE,
                    )
                )

        # Crear las nuevas relaciones en lote (bulk_create)
        if task_users:
            TaskXusers.objects.bulk_create(task_users)

        # Actualizar las relaciones existentes a ACTIVE
        if task_users_to_update:
            TaskXusers.objects.bulk_update(task_users_to_update, ["state"])

    @classmethod
    def remove_user_from_task(cls, task: Task, users: list[User]) -> bool:
        try:
            task_users = cls.objects.filter(task=task, user__in=users)
            cls.objects.bulk_update(task_users, [{"state": TaskXusers.INACTIVE}])
            return True
        # pylint: disable=broad-except
        except Exception:
            return False

    class Meta:
        db_table = "TASKS_X_USERS"
        verbose_name = "Tarea por usuario"
        verbose_name_plural = "Tareas por usuarios"
        constraints = [
            models.UniqueConstraint(fields=["task", "user"], name="unique_task_x_user")
        ]


class Tags(BaseModels):
    STATE_CHOICES = STATE_CHOICES
    tag_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=100, null=True, blank=True)
    color = models.CharField(max_length=7, null=True, blank=True)

    def __str__(self):
        return f"{self.pk} - {self.name}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def mormalize_color(self) -> SafeText:
        return format_html(
            f"""<div
                    style="background-color: {self.color};
                        width: 50px;
                        height: 15px;
                        border-radius: 5px;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        padding: 5px;
                    "
                >
                    {self.color}
                </div>"""
        )

    mormalize_color.short_description = "Color"

    class Meta:
        db_table = "TAGS"
        verbose_name = "Tag"
        verbose_name_plural = "Tags"


class TagXTasks(BaseModels):
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="%(class)s_task"
    )
    tag = models.ForeignKey(
        Tags, on_delete=models.CASCADE, related_name="%(class)s_tag"
    )

    def __str__(self):
        return f"{self.pk} - {self.task} - {self.tag}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.task!r} - {self.tag!r})"

    def get_task_name(self):
        return self.task.name

    def get_tag_name(self):
        return self.tag.name

    get_tag_name.short_description = "Tag"
    get_task_name.short_description = "Task"

    class Meta:
        db_table = "TAGS_X_TASKS"
        verbose_name = "Etiqueta por tarea"
        verbose_name_plural = "Etiquetas por tareas"
        constraints = [
            models.UniqueConstraint(fields=["task", "tag"], name="unique_tag_x_task")
        ]
