from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from core.settings import PATH_BASE
from dashboard import views


BASE_DASHBOARD_PATH = f"{PATH_BASE}dashboard/"

get_recent_activities = views.DashboardViewSet.as_view(
    {"post": "get_recent_activities"}
)
get_employees_by_department = views.DashboardViewSet.as_view(
    {"get": "get_employees_by_department"}
)
task_performance = views.DashboardViewSet.as_view({"post": "task_performance"})
get_user_statistic = views.DashboardViewSet.as_view({"get": "get_user_statistic"})
salary_by_department = views.DashboardViewSet.as_view({"get": "salary_by_department"})
get_employes_by_month = views.DashboardViewSet.as_view({"get": "get_employes_by_month"})
get_payroll_payment_detail = views.DashboardViewSet.as_view(
    {"get": "get_payroll_payment_detail"}
)


urlpatterns = [
    path(f"{BASE_DASHBOARD_PATH}get_recent_activities", get_recent_activities),
    path(f"{BASE_DASHBOARD_PATH}task_performance/", task_performance),
    path(f"{BASE_DASHBOARD_PATH}get_user_statistic/", get_user_statistic),
    path(f"{BASE_DASHBOARD_PATH}salary_by_department/", salary_by_department),
    path(f"{BASE_DASHBOARD_PATH}get_employes_by_month/", get_employes_by_month),
    path(
        f"{BASE_DASHBOARD_PATH}get_payroll_payment_detail/", get_payroll_payment_detail
    ),
    path(
        f"{BASE_DASHBOARD_PATH}get_employees_by_department/",
        get_employees_by_department,
    ),
]


urlpatterns = format_suffix_patterns(urlpatterns)
