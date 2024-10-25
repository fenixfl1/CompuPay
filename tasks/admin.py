from django.contrib import admin

from helpers.admin import BaseModelAdmin
from tasks.models import TagXTasks, Tags, Task, TaskXusers


class TaskAdmin(BaseModelAdmin):
    list_display = (
        "task_id",
        "name",
        "get_assigned_users",
        "completed",
        "priority",
        "start_date",
        "end_date",
    )
    search_fields = ("name", "completed", "priority")
    list_filter = ("completed", "priority")


class TagsAdmin(BaseModelAdmin):
    list_display = (
        "tag_id",
        "name",
        "description",
        "mormalize_color",
    )
    search_fields = ("name", "description")
    list_filter = ("name", "description")


class TagXTasksAdmin(BaseModelAdmin):
    list_display = (
        "get_tag_name",
        "get_task_name",
    )
    search_fields = ("task", "tag")
    list_filter = ("task", "tag")


class TaskxusersAdmin(BaseModelAdmin):
    list_display = (
        "task",
        "user",
    )
    search_fields = ("task", "user")


admin.site.register(Task, TaskAdmin)
admin.site.register(Tags, TagsAdmin)
admin.site.register(TagXTasks, TagXTasksAdmin)
admin.site.register(TaskXusers, TaskxusersAdmin)
