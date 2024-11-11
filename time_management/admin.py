from django.contrib import admin

from helpers.admin import BaseModelAdmin
from time_management.models import Leaves, Overtime


class OvertimeAdmin(BaseModelAdmin):
    list_filter = ("state",)
    list_display = ("overtime_id",
                    "employee",
                    "date",
                    "hours",
                    "rate",
                    "paid",
                    "comment",
                    "concept",
                    )


class LeaveAdmin(BaseModelAdmin):
    list_display = (
        "leave_id",
        "employee",
        "start_date",
        "end_date",
        "days",
        "comment",
        "amount",
        "is_paid"
    )
    list_filter = ("state", "employee")


admin.site.register(Overtime, OvertimeAdmin)
admin.site.register(Leaves, LeaveAdmin)
