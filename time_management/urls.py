from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from time_management import views
from core.settings import PATH_BASE


BASE_PATH_TIME_MANAGEMENT = f"{PATH_BASE}time_management/"

create_leave = views.LeavesViewSet.as_view({"post": "create_leave"})
update_leave = views.LeavesViewSet.as_view({"put": "update_leave"})
get_leaves = views.LeavesViewSet.as_view({"post": "get_leaves"})
get_leave = views.LeavesViewSet.as_view({"get": "get_leave"})

create_overtime = views.OvertimeViewSet.as_view({"post": "create_overtime"})
update_overtime = views.OvertimeViewSet.as_view({"put": "update_overtime"})
get_overtimes = views.OvertimeViewSet.as_view({"post": "get_overtimes"})
get_overtime = views.OvertimeViewSet.as_view({"get": "get_overtime"})


urlpatterns = [
    path(f"{BASE_PATH_TIME_MANAGEMENT}get_leave/<int:leave_id>", get_leave),
    path(f"{BASE_PATH_TIME_MANAGEMENT}create_leave/", create_leave),
    path(f"{BASE_PATH_TIME_MANAGEMENT}update_leave/", update_leave),
    path(f"{BASE_PATH_TIME_MANAGEMENT}get_leaves/", get_leaves),
    path(f"{BASE_PATH_TIME_MANAGEMENT}create_overtime/", create_overtime),
    path(f"{BASE_PATH_TIME_MANAGEMENT}update_overtime/", update_overtime),
    path(f"{BASE_PATH_TIME_MANAGEMENT}get_overtimes/", get_overtimes),
    path(f"{BASE_PATH_TIME_MANAGEMENT}get_overtime/<int:overtime_id>", get_overtime),
]

urlpatterns = format_suffix_patterns(urlpatterns)
