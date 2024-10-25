import datetime
from django import forms

from helpers.common import BaseModelForm
from payroll.models import Payroll, PayrollSettings


class PayrollForm(BaseModelForm):
    class Meta:
        model = Payroll
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings = PayrollSettings.objects.first()

        if settings:
            self.fields["period_start"].initial = datetime.date.today()
