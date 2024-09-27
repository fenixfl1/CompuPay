from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from core.settings import PATH_BASE
from tasks import views

BASE_PATH_TASKS = f"{PATH_BASE}tasks/"

create_task = views.TaskViewSet.as_view({"post": "create_task"})
update_task = views.TaskViewSet.as_view({"put": "update_task"})
get_tasks_list = views.TaskViewSet.as_view({"post": "get_tasks_list"})
get_task = views.TaskViewSet.as_view({"post": "get_task"})
get_tags_list = views.TaskViewSet.as_view({"post": "get_tags_list"})
create_tag = views.TaskViewSet.as_view({"post": "create_tag"})
update_tag = views.TaskViewSet.as_view({"put": "update_tag"})
update_task_state = views.TaskViewSet.as_view({"put": "update_task_state"})
add_or_remove_user = views.TaskViewSet.as_view({"post": "add_or_remove_user"})

urlpatterns = [
    path(f"{BASE_PATH_TASKS}create_task/", create_task),
    path(f"{BASE_PATH_TASKS}update_task/", update_task),
    path(f"{BASE_PATH_TASKS}get_tasks_list", get_tasks_list),
    path(f"{BASE_PATH_TASKS}get_task/", get_task),
    path(f"{BASE_PATH_TASKS}get_tags_list/", get_tags_list),
    path(f"{BASE_PATH_TASKS}create_tag/", create_tag),
    path(f"{BASE_PATH_TASKS}update_tag/", update_tag),
    path(f"{BASE_PATH_TASKS}update_task_state/", update_task_state),
    path(f"{BASE_PATH_TASKS}add_or_remove_user/", add_or_remove_user),
]

urlpatterns = format_suffix_patterns(urlpatterns)
