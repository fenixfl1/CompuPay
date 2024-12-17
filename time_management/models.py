from decimal import Decimal
from django.db import models

from helpers.models import BaseModels
from users.models import User


class Overtime(BaseModels):
    """
    `TBALE NAME`: OVERTIME
    """

    overtime_id = models.AutoField(primary_key=True, auto_created=True)
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    comment = models.TextField(blank=True, null=True)
    concept = models.ForeignKey(
        "payroll.Concept",
        on_delete=models.CASCADE,
        related_name="%(class)s_concept",
        db_column="concept_id",
        to_field="concept_id",
        blank=True,
        null=True,
    )
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s_user",
        db_column="employee",
        to_field="username",
    )

    class Meta:
        db_table = "OVERTIME"
        verbose_name = "Hora Extra"
        verbose_name_plural = "Horas Extras"
        ordering = ["-overtime_id"]

    def __str__(self) -> str:
        return (
            f"{self.hours} horas extras para {self.employee.full_name()} el {self.date}"
        )

    def get_amount(self) -> Decimal:
        return self.rate * self.hours


class Leaves(BaseModels):
    """
    This table represents permissión, vations, and others\n
    `TABLE NAME:` LEAVES
    """

    STATE_CHOICES = (("A", "Activo"), ("I", "Inactivo"), ("D", "Completada"))
    DONE = "D"
    PENDING = "A"
    PAYMENT_TYPES = (("Completo", "C"), ("Parcial", "P"), ("No Remunerado", "N"))
    LEAVES_REASON = (
        ("Vacaciones", "V"),
        ("Salud", "S"),
        ("Otro", "O"),
        ("Ausencia", "A"),
    )

    REQUIRED_FIELDS = ["start_date", "end_date", "days", "reason", "employee"]
    ALLOWED_FIELDS = ["leave_id"] + REQUIRED_FIELDS

    leave_id = models.AutoField(primary_key=True, auto_created=True)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.IntegerField()
    comment = models.TextField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s_user",
        db_column="employee",
        to_field="username",
    )
    concept = models.ForeignKey(
        "payroll.Concept",
        on_delete=models.CASCADE,
        related_name="%(class)s_concept",
        db_column="concept_id",
        to_field="concept_id",
        blank=True,
        null=True,
    )
    state = models.CharField(
        default="A", max_length=1, null=False, choices=STATE_CHOICES
    )

    class Meta:
        db_table = "LEAVES"
        verbose_name = "Vacaión, Permiso y Aucencia"
        verbose_name_plural = "Vacaiones, Permisos y Aucencias"
        ordering = ["-leave_id"]

    def __str__(self):
        reasons = dict(self.LEAVES_REASON)
        return f"{reasons.get(self.concept.name, '')}\
            {self.employee.full_name()} del {self.start_date} al {self.end_date}"
