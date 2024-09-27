from datetime import datetime
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from django.core.management.base import BaseCommand


def setup_periodic_tasks():
    # Crea o actualiza la programación de la tarea
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="0",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
    )

    PeriodicTask.objects.update_or_create(
        crontab=schedule,
        name="Process Payroll",
        task="payroll.tasks.process_payroll",
        defaults={"start_time": datetime.now()},
    )


class Command(BaseCommand):
    help = "Set up periodic tasks for the payroll system"

    def handle(self, *args, **kwargs):
        setup_periodic_tasks()  # Ejecuta el código para configurar las tareas
        self.stdout.write(self.style.SUCCESS("Successfully set up tasks"))
