from typing import Any
from django.db import models
from django.utils.html import format_html
from django.utils.safestring import SafeText

from helpers.models import STATE_CHOICES, BaseModels
from users.models import User


class Task(BaseModels):
    STATE_CHOICES = STATE_CHOICES
    STATUS_CHOICES = (
        ("D", "Done"),
        ("P", "Pending"),
        ("I", "In Progress"),
        ("C", "Canceled"),
    )
    PRIORITY_CHOICES = (
        ("H", "High"),
        ("M", "Medium"),
        ("L", "Low"),
    )

    task_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=1, default="P", choices=STATUS_CHOICES)
    priority = models.CharField(
        max_length=1, null=True, blank=True, choices=PRIORITY_CHOICES
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    assigned_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        to_field="username",
        related_name="%(class)s_assigned_user",
        db_column="assigned_user",
    )
    tags = models.ManyToManyField(
        "Tags",
        through="TagXTasks",
        through_fields=("task", "tag"),
        related_name="%(class)s_tags",
    )

    def __str__(self):
        return f"{self.pk} - {self.name}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    class Meta:
        db_table = "TASKS"
        verbose_name = "Task"
        verbose_name_plural = "Tasks"


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
