from django.contrib import admin

from helpers.admin import BaseModelAdmin
from payroll.forms import PayrollForm
from payroll.models import (
    Concept,
    DeductionXuser,
    Deductions,
    Payroll,
    PayrollEntry,
    Adjustment,
    PayrollPaymentDetail,
    PayrollSettings,
)


class PayrollAdmin(BaseModelAdmin):
    form = PayrollForm

    list_display = ("payroll_id", "period_start", "period_end", "status")
    search_fields = ("name", "state")
    list_filter = ("state",)


class PayrollSettingAdmin(BaseModelAdmin):
    list_display = ("periods", "autopay")


class PayrollEntryAdmin(BaseModelAdmin):
    list_display = (
        "payroll_entry_id",
        "payroll",
        "user",
        "get_status",
    )
    search_fields = ("payroll", "user", "status")
    list_filter = ("status", "payroll")


class DeductionsAdmin(BaseModelAdmin):
    list_display = (
        "deduction_id",
        "name",
        "description",
        "percentage",
    )
    search_fields = ("name", "description")


class DeductionXuserAdmin(BaseModelAdmin):
    list_display = (
        "user",
        "deduction",
    )
    search_fields = ("user", "deduction")
    list_filter = (
        "state",
        "user",
        "deduction",
    )


class AdjustmentAdmin(BaseModelAdmin):
    list_display = (
        "adjustment_id",
        "payroll_entry",
        "amount",
        "description",
        "type",
        "concept",
    )
    search_fields = ("payroll_entry", "amount", "description")
    list_filter = ("payroll_entry__payroll",)
    list_editable = ("concept",)


class ConceptsAdmin(BaseModelAdmin):
    list_display = ("concept_id", "name", "description")


class PayrollPaymentDetailAdmin(BaseModelAdmin):
    list_filter = ("payroll", "payroll_entry", "concept")
    list_display = (
        "payroll",
        "get_meployee_name",
        "concept",
        "period",
        "concept_amount",
        "gross_salary",
        "comment",
    )


class PayrollSettingsAdmin(BaseModelAdmin):
    list_display = ("periods", "autopay", "deduction_period")


admin.site.register(Payroll, PayrollAdmin)
admin.site.register(PayrollEntry, PayrollEntryAdmin)
admin.site.register(Deductions, DeductionsAdmin)
admin.site.register(DeductionXuser, DeductionXuserAdmin)
admin.site.register(Adjustment, AdjustmentAdmin)
admin.site.register(Concept, ConceptsAdmin)
admin.site.register(PayrollPaymentDetail, PayrollPaymentDetailAdmin)
admin.site.register(PayrollSettings, PayrollSettingsAdmin)
