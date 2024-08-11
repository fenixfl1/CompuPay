from django.contrib import admin

from helpers.admin import BaseModelAdmin
from tasks.models import TagXTasks, Tags, Task


class TaskAdmin(BaseModelAdmin):
    list_display = (
        "task_id",
        "name",
        "status",
        "priority",
        "start_date",
        "end_date",
        "assigned_user",
    )
    search_fields = ("name", "status", "priority")
    list_filter = ("status", "priority")


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


admin.site.register(Task, TaskAdmin)
admin.site.register(Tags, TagsAdmin)
admin.site.register(TagXTasks, TagXTasksAdmin)
