from django.db.models import Q
from celery import shared_task
from .models import Payroll, PayrollEntry, PayrollSettings


@shared_task
def autopay_payroll():
    try:
        settings = PayrollSettings.objects.filter(
            Q(autopay=True) & Q(state="A")
        ).first()
        if settings:
            payroll = Payroll.objects.filter(
                Q(status=Payroll.PENDING) & Q(state="A")
            ).first()
            entries = PayrollEntry.objects.filter(
                Q(state="A") & Q(payroll_id=payroll.payroll_id)
            )
            for entry in entries:
                entry.status = True
                entry.save()

            Payroll.autostart_payroll(settings.created_by)
    # pylint: disable=broad-except
    except Exception:
        pass
