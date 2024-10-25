from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from core.settings import PATH_BASE
from payroll import views

BASE_PAYROLL_PATH = f"{PATH_BASE}payroll/"

create_payroll = views.PayrollViewSet.as_view({"post": "create_payroll"})
update_payroll = views.PayrollViewSet.as_view({"put": "update_payroll"})
get_payrolls = views.PayrollViewSet.as_view({"post": "get_payrolls"})
get_payroll = views.PayrollViewSet.as_view({"post": "get_payroll"})
get_payroll_entries = views.PayrollViewSet.as_view({"post": "get_payroll_entries"})
create_payroll_entry = views.PayrollViewSet.as_view({"post": "create_payroll_entry"})
update_payroll_entry = views.PayrollViewSet.as_view({"put": "update_payroll_entry"})
get_payroll_entry = views.PayrollViewSet.as_view({"get": "get_payroll_entry"})
create_adjustment = views.PayrollViewSet.as_view({"post": "create_adjustment"})
update_adjustment = views.PayrollViewSet.as_view({"put": "update_adjustment"})
get_adjustments = views.PayrollViewSet.as_view({"post": "get_adjustments"})
get_deduction_list = views.PayrollViewSet.as_view({"post": "get_deduction_list"})
process_payroll = views.PayrollViewSet.as_view({"post": "process_payroll"})
get_payroll_info = views.PayrollViewSet.as_view({"get": "get_payroll_info"})
get_payroll_history = views.PayrollViewSet.as_view({"post": "get_payroll_history"})
process_partial_payroll = views.PayrollViewSet.as_view(
    {"post": "process_partial_payroll"}
)


urlpatterns = [
    path(f"{BASE_PAYROLL_PATH}create_payroll/", create_payroll),
    path(f"{BASE_PAYROLL_PATH}update_payroll/", update_payroll),
    path(f"{BASE_PAYROLL_PATH}get_payrolls/", get_payrolls),
    path(f"{BASE_PAYROLL_PATH}get_payroll/<int:payroll_id>/", get_payroll),
    path(f"{BASE_PAYROLL_PATH}get_payroll_entries/", get_payroll_entries),
    path(f"{BASE_PAYROLL_PATH}create_payroll_entry/", create_payroll_entry),
    path(f"{BASE_PAYROLL_PATH}update_payroll_entry/", update_payroll_entry),
    path(f"{BASE_PAYROLL_PATH}get_payroll_entry/<int:entry_id>/", get_payroll_entry),
    path(f"{BASE_PAYROLL_PATH}create_adjustment/", create_adjustment),
    path(f"{BASE_PAYROLL_PATH}update_adjustment/", update_adjustment),
    path(f"{BASE_PAYROLL_PATH}get_adjustments/", get_adjustments),
    path(f"{BASE_PAYROLL_PATH}get_deduction_list/", get_deduction_list),
    path(f"{BASE_PAYROLL_PATH}get_payroll/", get_payroll),
    path(f"{BASE_PAYROLL_PATH}process_payroll/", process_payroll),
    path(f"{BASE_PAYROLL_PATH}get_payroll_info/", get_payroll_info),
    path(f"{BASE_PAYROLL_PATH}process_partial_payroll/", process_partial_payroll),
    path(f"{BASE_PAYROLL_PATH}get_payroll_history", get_payroll_history),
]

urlpatterns = format_suffix_patterns(urlpatterns)
