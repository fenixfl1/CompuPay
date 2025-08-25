# pylint: disable=no-member

import locale
import datetime
from typing import Iterable
from datetime import timedelta
from decimal import Decimal, getcontext
from django.db import IntegrityError, models, transaction
from django.db.models import Q, Max
from django.forms import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from rest_framework.request import Request
from rest_framework.exceptions import APIException

from helpers.exceptions import PayloadValidationError
from helpers.models import BaseModels
from helpers.utils import format_date, ordinal
from time_management.models import Leaves, Overtime
from users.models import User


locale.setlocale(locale.LC_TIME, "Spanish_Spain.1252")

getcontext().prec = 2


class Payroll(BaseModels):
    """
    Payroll model\n
    `TABLE_NAME`: PAYROLL
    """

    STATUS_CHOICES = (("P", "Pendiente"), ("F", "Finalizada"))
    PENDING = "P"
    DONE = "F"

    payroll_id = models.AutoField(primary_key=True)
    period_start = models.DateField()
    period_end = models.DateField()
    period = models.IntegerField(default=1, unique_for_month=True)
    includes_overtime = models.BooleanField(default=False)
    includes_leaves = models.BooleanField(default=False)
    status = models.CharField(
        max_length=1, blank=True, null=True, choices=STATUS_CHOICES, default=PENDING
    )

    REQUIRED_FIELDS = ["period_start", "period_end", "state"]
    ALLOWED_FIELDS = REQUIRED_FIELDS + [
        "payroll_id",
        "employees",
        "includes_overtime",
        "includes_leaves",
    ]

    def __str__(self):
        config = self.get_config()
        month = self.period_start.strftime("%B")
        if config.periods == 1:
            return f"Nómina de {month}"
        return f"{ordinal(self.period)} Nómina de {month.capitalize()}"

    def next_payment(self) -> str:
        return format_date(self.period_end).capitalize()

    @classmethod
    def get_config(cls) -> "PayrollSettings":
        return PayrollSettings.objects.filter(Q(state=PayrollSettings.ACTIVE)).first()

    @transaction.atomic
    def create_payroll(self, request, **kwargs) -> "Payroll":
        payroll_count = Payroll.objects.all().count()
        kwargs["payroll_id"] = payroll_count + 1
        employee = kwargs.pop("employees", "__all__")

        current_date = datetime.datetime.now()
        start_month = timezone.make_aware(current_date.replace(day=1))

        existing_payrolls_in_month = Payroll.objects.filter(
            period_start__gte=start_month
        ).count()

        settings = Payroll.get_config()
        if not settings:
            raise ValidationError("No se encontró una configuración de nómina activa")

        if existing_payrolls_in_month >= settings.periods:
            raise ValidationError(
                f"Ya se han creado los {settings.periods} permitidos este mes"
            )

        kwargs["period"] = existing_payrolls_in_month + 1

        self.clean()
        payroll = super().create(request, **kwargs)

        employees = None
        employee_query = (
            Q(is_active=True)
            & Q(is_staff=True)
            & Q(state=User.ACTIVE)
            & Q(salary__gt=0)
        )
        if isinstance(employee, str) and employee == "__all__":
            employees = User.objects.filter(employee_query)
        elif isinstance(employee, list):
            employees = User.objects.filter(Q(username__in=employee) & employee_query)
        else:
            raise PayloadValidationError(
                "Invalid employees field",
            )
        PayrollEntry.create_entries(payroll, employees, request.user)

    @transaction.atomic
    def process_payroll(
        self, request: Request, users_id: list[int] = None
    ) -> "Payroll":
        settings = self.get_config()
        apply_deduction = settings.periods == self.period
        payroll_entries = PayrollEntry.objects.filter(payroll_id=self.payroll_id)
        if users_id:
            payroll_entries = payroll_entries.filter(user__user_id__in=users_id)

        for entry in payroll_entries:
            # === OTRAS DEDUCCIONES ASIGNADAS (excluye AFP/SFS/ISR) ===
            other_assigned_deductions_total = Decimal("0.00")
            if apply_deduction:
                deduction_user = DeductionXuser.get_user_deductions(entry.user)
                if deduction_user:
                    for du in deduction_user:
                        name = (du.deduction.name or "").upper()
                        if name in {"AFP", "SFS", "ISR"}:
                            # Se calculan y crean aparte, de forma automática
                            continue

                        amount = DeductionXuser.get_deduction_amount(
                            entry.user, du.deduction.name
                        )
                        PayrollPaymentDetail.objects.create(
                            payroll=entry.payroll,
                            payroll_entry=entry,
                            concept=du.deduction.concept,
                            period=self.period,
                            concept_amount=amount,
                            state=PayrollPaymentDetail.ACTIVE,
                            created_by=request.user,
                            gross_salary=entry.user.salary,
                            comment=f"Descuento mensual por concepto de {du.deduction.name}",
                            operator="-",
                        )
                        # Importante: lo restamos del neto
                        other_assigned_deductions_total += amount or Decimal("0.00")

            # === AJUSTES / BONOS ===
            adjustments = Adjustment.get_by_entry(entry)
            if adjustments:
                for adjustment in adjustments:
                    PayrollPaymentDetail.objects.create(
                        payroll=entry.payroll,
                        payroll_entry=entry,
                        concept=adjustment.concept,
                        period=self.period,
                        concept_amount=Adjustment.get_amount(entry, adjustment.concept),
                        state=PayrollPaymentDetail.ACTIVE,
                        created_by=request.user,
                        gross_salary=entry.user.salary,
                        comment=adjustment.description,
                        operator=adjustment.concept.operator,
                    )
                Adjustment.objects.filter(id__in=[a.id for a in adjustments]).update(
                    state=Adjustment.COMPLETED
                )

            # === HORAS EXTRAS ===
            total_overtime_amount = Decimal("0.0")
            total_hours = Decimal("0.0")
            overtimes = entry.get_employee_overtime()
            if self.includes_overtime and overtimes:
                concept = overtimes.first().concept
                for overtime in overtimes:
                    amount = overtime.get_amount()
                    total_overtime_amount += amount
                    total_hours += overtime.hours
                    overtime.paid = True

                PayrollPaymentDetail.objects.create(
                    payroll=entry.payroll,
                    payroll_entry=entry,
                    concept=concept,
                    period=self.period,
                    concept_amount=total_overtime_amount,
                    state=PayrollPaymentDetail.ACTIVE,
                    created_by=request.user,
                    gross_salary=entry.user.salary,
                    comment=f"{total_hours} horas por un total de:",
                    operator="+",
                )
                Overtime.objects.bulk_update(overtimes, ["paid"])

            # === LICENCIAS (pagadas y con descuento) ===
            total_paid_leaves = Decimal("0.0")
            total_discount_leaves = Decimal("0.0")

            paid_leaves = entry.get_leaves()
            if self.includes_leaves and paid_leaves:
                for leave in paid_leaves:
                    leave.state = Leaves.DONE
                    total_paid_leaves += leave.amount
                    PayrollPaymentDetail.objects.create(
                        payroll=entry.payroll,
                        payroll_entry=entry,
                        concept=leave.concept,
                        period=self.period,
                        concept_amount=leave.amount,
                        state=PayrollPaymentDetail.ACTIVE,
                        created_by=request.user,
                        gross_salary=entry.user.salary,
                        comment=f"Pago por concepto de {leave.concept.name}",
                        operator="+",
                    )
                Leaves.objects.bulk_update(paid_leaves, ["state"])

                discounted_leaves = entry.get_leaves(False)
                for discount in discounted_leaves:
                    discount.state = Leaves.DONE
                    total_discount_leaves += discount.amount
                    PayrollPaymentDetail.objects.create(
                        payroll=entry.payroll,
                        payroll_entry=entry,
                        concept=discount.concept,
                        period=self.period,
                        concept_amount=discount.amount,
                        state=PayrollPaymentDetail.ACTIVE,
                        created_by=request.user,
                        gross_salary=entry.user.salary,
                        comment=f"Descuento por concepto de {discount.concept.name}",
                        operator="-",
                    )
                # FIX: actualizar el conjunto correcto
                Leaves.objects.bulk_update(discounted_leaves, ["state"])

            # === TOTALES VARIABLES ===
            discount = Adjustment.calc_deduction(entry) + total_discount_leaves

            bonus = Adjustment.calc_bonus(entry)

            # === DEDUCCIONES DE LEY (AFP/SFS/ISR automáticas) ===
            afp = (
                DeductionXuser.get_afp(entry.user)
                if apply_deduction
                else Decimal("0.0")
            )
            sfs = (
                DeductionXuser.get_sfs(entry.user)
                if apply_deduction
                else Decimal("0.0")
            )

            # ISR dinámico: salario del mes + extras (bonos + horas extras + licencias pagadas) - AFP - SFS
            extra_income_for_isr = bonus + total_overtime_amount
            isr = (
                DeductionXuser.get_isr(entry.user, extra_income=extra_income_for_isr)
                if apply_deduction
                else Decimal("0.0")
            )

            # Crear detalles explícitos de AFP / SFS / ISR
            if apply_deduction:
                if afp and afp != Decimal("0.0"):
                    concept_afp = Concept.objects.filter(name="AFP").first()
                    PayrollPaymentDetail.objects.create(
                        payroll=entry.payroll,
                        payroll_entry=entry,
                        concept=concept_afp,
                        period=self.period,
                        concept_amount=afp,
                        state=PayrollPaymentDetail.ACTIVE,
                        created_by=request.user,
                        gross_salary=entry.user.salary,
                        comment="Descuento mensual por concepto de AFP",
                        operator="-",
                    )
                if sfs and sfs != Decimal("0.0"):
                    concept_sfs = Concept.objects.filter(name="SFS").first()
                    PayrollPaymentDetail.objects.create(
                        payroll=entry.payroll,
                        payroll_entry=entry,
                        concept=concept_sfs,
                        period=self.period,
                        concept_amount=sfs,
                        state=PayrollPaymentDetail.ACTIVE,
                        created_by=request.user,
                        gross_salary=entry.user.salary,
                        comment="Descuento mensual por concepto de SFS",
                        operator="-",
                    )
                if isr and isr != Decimal("0.0"):
                    concept_isr = Concept.objects.filter(name="ISR").first()
                    PayrollPaymentDetail.objects.create(
                        payroll=entry.payroll,
                        payroll_entry=entry,
                        concept=concept_isr,
                        period=self.period,
                        concept_amount=isr,
                        state=PayrollPaymentDetail.ACTIVE,
                        created_by=request.user,
                        gross_salary=entry.user.salary,
                        comment="Descuento mensual por concepto de ISR (automático)",
                        operator="-",
                    )

            # === SALARIO NETO ===
            salary = entry.user.salary / settings.periods
            net_salary = (
                (salary + bonus + total_overtime_amount + total_paid_leaves)
                - discount  # ajustes de tipo deducción + licencias con descuento
                - other_assigned_deductions_total  # OTRAS deducciones asignadas (≠ AFP/SFS/ISR)
                - afp
                - sfs
                - isr
            )

            salary_concept = Concept.objects.get(name="SALARIO")
            PayrollPaymentDetail.objects.create(
                payroll=entry.payroll,
                payroll_entry=entry,
                concept=salary_concept,
                period=self.period,
                concept_amount=net_salary,
                state=PayrollPaymentDetail.ACTIVE,
                created_by=request.user,
                gross_salary=entry.user.salary,
                operator=salary_concept.operator,
            )

            payroll_entries.update(status=True)

        return self

    def save(self, *args, **kwargs):
        self.clean()  # Llama a clean antes de guardar
        super().save(*args, **kwargs)

    class Meta:
        db_table = "PAYROLL"
        verbose_name = "Nómina"
        verbose_name_plural = "Nóminas"
        ordering = ["-payroll_id"]


class Concept(BaseModels):
    """
    This model represents the concepts for each payroll entry payment.\n
    Each kind of discount or deduction have an concept: Example bonus, discount, text, etc..\n
    `TABLE_NAME` CONCEPTS
    """

    OPERATOR_CHOISES = (("+", "Suma"), ("-", "Resta"), (None, "Ninguno"))

    concept_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=20, null=False, blank=False, unique=False)
    operator = models.CharField(
        max_length=1, null=True, blank=True, default="-", choices=OPERATOR_CHOISES
    )
    description = models.CharField(max_length=250, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name}"

    class Meta:
        db_table = "CONCEPTS"
        verbose_name = "Concepto"
        verbose_name_plural = "Conceptos"


class PayrollSettings(BaseModels):
    """
    This model is use to configure the payroll
    `TABLE_NAME:` PAYROLL_SETTINGS
    """

    PERIOD_CHOICES = ((1, "Mensual"), (2, "Quincenal"), (4, "Semanal"))
    DEDUCTION_PERIOD_CHOICES = (
        (1, "Primero"),
        (2, "Segundo"),
        (3, "Tercero"),
        (4, "Cuarto"),
    )

    periods = models.IntegerField(default=1, choices=PERIOD_CHOICES)
    autopay = models.BooleanField(default=False)
    deduction_period = models.IntegerField(
        default=2,
        choices=DEDUCTION_PERIOD_CHOICES,
        help_text="Período en el que se deben hacer los descuentos de ley",
    )

    def __str__(self):
        return f"Configuración Nómina - {self.pk}"

    def __repr__(self):
        return f"Las deducciones se descuentan en la {self.get_deduction_period_display()} Nómina de cada mes"

    def clean(self):
        super().clean()

        # Desactivar todas las configuraciones activas antes de guardar la nueva
        PayrollSettings.objects.filter(state="A").update(state="I")

    class Meta:
        db_table = "PAYROLL_SETTINGS"
        verbose_name = "Configuración de Nómina"
        verbose_name_plural = "Configuraciones de Nómina"
        ordering = ["-created_at"]


class PayrollEntry(BaseModels):
    """
    Payroll Entry model\n
    `TABLE_NAME`: PAYROLL_ENTRY
    """

    payroll_entry_id = models.AutoField(primary_key=True)
    payroll = models.ForeignKey(
        Payroll,
        on_delete=models.CASCADE,
        related_name="%(class)s_payroll",
        db_column="payroll_id",
        to_field="payroll_id",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s_user",
        db_column="user",
        to_field="username",
    )
    status = models.BooleanField(default=False)

    REQUIRED_FIELDS = ["payroll_id", "employees", "state"]
    ALLOWED_FIELDS = REQUIRED_FIELDS + ["status"]

    def __str__(self):
        return f"@{self.user.username}"

    def get_employee_overtime(self):
        return Overtime.objects.filter(
            Q(state=Overtime.ACTIVE)
            & Q(paid=False)
            & Q(employee__username=self.user.username)
        )

    def get_leaves(self, is_paid: bool = True):
        return Leaves.objects.filter(
            Q(state=Leaves.ACTIVE)
            & Q(amount__gt=0)
            & Q(is_paid=is_paid)
            & Q(employee__username=self.user.username)
        )

    @classmethod
    def create_entries(
        cls, payroll: Payroll, employees: list[User], current_user: User
    ) -> list["PayrollEntry"]:
        try:
            entries: list[PayrollEntry] = []
            counter = cls.objects.all().count()
            for employee in employees:
                counter += 1
                entries.append(
                    PayrollEntry(
                        payroll_entry_id=counter,
                        payroll=payroll,
                        user=employee,
                        state="A",
                        created_by=current_user,
                    )
                )
            cls.objects.bulk_create(entries)
        except IntegrityError as e:
            raise ValidationError(
                "Uno  o mas empleados ya esta incluidos en esta nomina",
                code="IntegrityError",
            ) from e

    def get_status(self):
        return "Pagado" if self.status else "Pendiente"

    get_status.short_description = "Estado de Pago"

    class Meta:
        db_table = "PAYROLL_ENTRY"
        verbose_name = "Entrada de Nómina"
        verbose_name_plural = "Entradas de Nómina"
        ordering = ["payroll_entry_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["payroll", "user"], name="unique_payroll_entry"
            )
        ]


class Adjustment(BaseModels):
    """
    Adjustment model\n
    `TABLE_NAME`: ADJUSTMENT
    """

    STATE_CHOICES = (("A", "Activo"), ("I", "Inactivo"), ("S", "Saldada"))
    ADJUSTMENT_TYPE = [
        ("B", "Bono"),
        ("D", "Descuento"),
    ]

    COMPLETED = "S"
    PENDING = "A"

    state = models.CharField(
        default="A", max_length=1, null=False, choices=STATE_CHOICES
    )
    adjustment_id = models.AutoField(primary_key=True)
    description = models.TextField(max_length=250)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payroll_entry = models.ForeignKey(
        PayrollEntry,
        on_delete=models.CASCADE,
        related_name="%(class)s_payroll_entry",
        db_column="payroll_entry_id",
        to_field="payroll_entry_id",
    )
    concept = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
        related_name="%(class)s_concept",
        db_column="concept_id",
        to_field="concept_id",
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"Ajuste de {self.payroll_entry.user.username}"

    @classmethod
    def calc_bonus(cls, entry: PayrollEntry) -> Decimal:
        bonus = Adjustment.objects.filter(
            Q(payroll_entry_id=entry.payroll_entry_id)
            & Q(concept__concept_id=4)
            & Q(state=Adjustment.ACTIVE)
        )

        total_bonus = Decimal("0.0")
        for bonu in bonus:
            total_bonus += bonu.amount
        return total_bonus

    @classmethod
    def calc_deduction(cls, entry: PayrollEntry) -> Decimal:
        deduction = Adjustment.objects.filter(
            Q(payroll_entry=entry) & Q(concept__concept_id=5)
        )
        total_deduction = Decimal("0.0")
        for deduc in deduction:
            total_deduction += deduc.amount
        return total_deduction

    @classmethod
    def get_amount(cls, entry: PayrollEntry, concept: str) -> Decimal:
        deduction = Adjustment.objects.filter(
            Q(payroll_entry=entry) & Q(concept=concept)
        )
        total_deduction = Decimal("0.0")
        for deduc in deduction:
            total_deduction += deduc.amount
        return total_deduction

    @classmethod
    def get_by_entry(cls, entry: PayrollEntry):
        return Adjustment.objects.filter(
            Q(payroll_entry=entry) & Q(state=Adjustment.ACTIVE)
        )

    def create_adjustment(self, request, **kwargs):
        adjustment_count = Adjustment.objects.all().count()
        kwargs["adjustment_id"] = adjustment_count + 1
        return super().create(request, **kwargs)

    class Meta:
        db_table = "ADJUSTMENT"
        verbose_name = "Beneficio y Deducción"
        verbose_name_plural = "Beneficios y Deducciones"


class Deductions(BaseModels):
    """
    Deduction model\n
    `TABLE_NAME`: DEDUCTIONS
    """

    ADJUSTMENT_TYPE = [
        ("SFS", "SFS - Seguro Familiar de Salud"),
        ("ISR", "ISR - Impuesto Sobre la Renta"),
        ("AFP", "AFP - Administradora de Fondos de Pensiones"),
    ]
    deduction_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, choices=ADJUSTMENT_TYPE)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.TextField(max_length=250)
    order = models.IntegerField(null=True, blank=True)
    salary_cap = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum salary amount to which \
            this deduction applies",
    )
    fixed_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    concept = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
        related_name="%(class)s_concept",
        db_column="concept_id",
        to_field="concept_id",
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"{self.name} - {self.percentage}"

    def create_deduction(self, request, **kwargs):
        deduction_count = self.objects.all().count()
        kwargs["deduction_id"] = deduction_count + 1
        super().create(request, **kwargs)

    class Meta:
        db_table = "DEDUCTIONS"
        verbose_name = "Retención"
        verbose_name_plural = "Retenciones"
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "percentage"],
                name="unique_deduction",
            ),
        ]


class DeductionXuser(BaseModels):
    """
    Deduction X User model\n
    This model represents the relationship between the deductions and the user\n
    `TABLE_NAME`: DEDUCTION_X_USER
    """

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="%(class)s_user",
        db_column="user",
        to_field="username",
    )
    deduction = models.ForeignKey(
        Deductions,
        on_delete=models.CASCADE,
        related_name="%(class)s_deduction",
        db_column="deduction_id",
        to_field="deduction_id",
    )

    def __str__(self) -> str:
        return f"{self.user.username} - {self.deduction.name}"

    @classmethod
    def has_deductions(cls, user: User, name: str = None) -> bool:
        deductions_user = DeductionXuser.objects.filter(
            Q(user_id=user.user_id) & Q(state=DeductionXuser.ACTIVE)
        )
        if name:
            return deductions_user.filter(deduction__name=name).exists()
        return deductions_user.exists()

    @classmethod
    def add_deductions_to_user(cls, deduction_ids, user, request: Request):
        """
        Sincroniza las deducciones de un usuario con el listado dado.

        - Activa las deducciones que estaban inactivas y fueron incluidas.
        - Crea las que no existían.
        - Inactiva las que no fueron incluidas en deduction_ids.
        """

        # 1. Obtener todas las deducciones actuales del usuario
        current_deductions = DeductionXuser.objects.filter(user=user)

        # 2. Activar las que vienen en deduction_ids pero están inactivas
        current_deductions.filter(deduction_id__in=deduction_ids, state="I").update(
            state="A"
        )

        print("*" * 75)
        print(
            f'{set(
                current_deductions.values_list("deduction_id", flat=True)
            )
            - set(deduction_ids)}'
        )
        print("*" * 75)

        # 3. Inactivar las que no están en deduction_ids
        current_deductions.filter(
            deduction_id__in=list(
                set(current_deductions.values_list("deduction_id", flat=True))
                - set(deduction_ids)
            )
        ).update(state="I")

        # 4. Crear nuevas deducciones que no existan
        existing_ids = current_deductions.values_list("deduction_id", flat=True)
        new_ids = set(deduction_ids) - set(existing_ids)

        DeductionXuser.objects.bulk_create(
            [
                DeductionXuser(
                    user=user,
                    deduction=Deductions.objects.get(deduction_id=ded_id),
                    state="A",
                    created_by=request.user,
                )
                for ded_id in new_ids
            ]
        )

    def create_deduction_user(self, request, **kwargs):
        deduction_user_count = self.objects.all().count()
        kwargs["id"] = deduction_user_count + 1
        super().create(request, **kwargs)

    @classmethod
    def get_user_deductions(cls, user: User, name: str = None):
        deduction_user = DeductionXuser.objects.filter(
            Q(state=DeductionXuser.ACTIVE) & Q(user__user_id=user.user_id)
        )
        if name:
            return deduction_user.filter(Q(deduction__name=name)).first()
        return deduction_user

    @classmethod
    def get_afp(cls, user: User) -> Decimal:
        user_deduction = DeductionXuser.get_user_deductions(user, "AFP")
        if user_deduction:
            deduction = Deductions.objects.filter(
                Q(name="AFP")
                & Q(state=Deductions.ACTIVE)
                & Q(deduction_id=user_deduction.deduction.deduction_id)
            ).first()
            if deduction:
                percentage = deduction.percentage
                base_salary = (
                    min(user.salary, deduction.salary_cap)
                    if deduction.salary_cap
                    else user.salary
                )
                return Decimal((base_salary * percentage) / 100).quantize(
                    Decimal("0.01")
                )
        return Decimal("0.00")

    @classmethod
    def get_sfs(cls, user: User) -> Decimal:
        user_deduction = DeductionXuser.get_user_deductions(user, "SFS")
        if user_deduction:
            deduction = Deductions.objects.filter(
                Q(name="SFS")
                & Q(state=Deductions.ACTIVE)
                & Q(deduction_id=user_deduction.deduction.deduction_id)
            ).first()
            if deduction:
                percentage = deduction.percentage
                base_salary = (
                    min(user.salary, deduction.salary_cap)
                    if deduction.salary_cap
                    else user.salary
                )
                return Decimal((base_salary * percentage) / 100).quantize(
                    Decimal("0.01")
                )
        return Decimal("0.00")

    @classmethod
    def get_isr(cls, user: User, extra_income: Decimal = Decimal("0.00")) -> Decimal:
        """
        Calcula ISR mensual dinámicamente:
        - Ignora lo asignado en DeductionXuser para ISR.
        - Determina el rango ISR por el salario anual imponible calculado a partir
          del salario mensual real (salario base + extras - AFP - SFS).
        - 'extra_income' debe incluir bonos y horas extras del mes.
        """

        # Deducciones de ley que reducen la base imponible
        afp = cls.get_afp(user)  # mantiene la lógica/cap actual
        sfs = cls.get_sfs(user)

        # Base mensual imponible: salario del mes + extras - AFP - SFS
        taxable_monthly_salary = (
            (user.salary + (extra_income or Decimal("0.00"))) - afp - sfs
        )
        if taxable_monthly_salary <= 0:
            return Decimal("0.00")

        taxable_annual_salary = taxable_monthly_salary * 12

        # Selección automática del rango ISR activo cuyo salary_cap sea <= a la base anual
        deduction = (
            Deductions.objects.filter(
                Q(name="ISR")
                & Q(state=Deductions.ACTIVE)
                & Q(salary_cap__lte=taxable_annual_salary)
            )
            .order_by("-salary_cap")
            .first()
        )

        if not deduction:
            return Decimal("0.00")

        base_salary_cap = deduction.salary_cap or Decimal("0.00")
        fixed_amount = getattr(deduction, "fixed_amount", None) or Decimal("0.00")
        percentage = (deduction.percentage or Decimal("0.00")) / 100

        # Fórmula de tramo: Monto fijo + (Excedente * %)
        isr_anual = (
            fixed_amount + (taxable_annual_salary - base_salary_cap) * percentage
            if taxable_annual_salary > base_salary_cap
            else Decimal("0.00")
        )

        # Devuelve ISR mensual
        return (isr_anual / 12).quantize(Decimal("0.01"))

    @classmethod
    def get_deduction_amount(cls, user: User, name: str):
        match name:
            case "ISR":
                return cls.get_isr(user)
            case "AFP":
                return cls.get_afp(user)
            case "SFS":
                return cls.get_sfs(user)
            case _:
                return 0.0

    class Meta:
        db_table = "DEDUCTION_X_USER"
        verbose_name = "Retención por Usuario"
        verbose_name_plural = "Retenciones por Usuario"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "deduction"], name="unique_deduction_user"
            )
        ]


class PayrollPaymentDetail(BaseModels):
    """
    This model is used to store payroll payment details\n
    `TABLE_NAME` PAYROLL_PAYMENT_DETAIL
    """

    OPERATOR_CHOISES = (("+", "Suma"), ("-", "Resta"))

    payroll = models.ForeignKey(
        Payroll,
        on_delete=models.CASCADE,
        related_name="%(class)s_payroll",
        db_column="payroll_id",
        to_field="payroll_id",
    )
    payroll_entry = models.ForeignKey(
        PayrollEntry,
        on_delete=models.CASCADE,
        related_name="%(class)s_payroll_entry",
        db_column="payroll_entry_id",
        to_field="payroll_entry_id",
    )
    concept = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
        related_name="%(class)s_concept",
        db_column="concept_id",
        to_field="concept_id",
        null=True,
        blank=True,
    )
    period = models.IntegerField(null=False, blank=False)
    concept_amount = models.DecimalField(decimal_places=2, max_digits=10)
    gross_salary = models.DecimalField(decimal_places=2, max_digits=10)
    comment = models.TextField(null=True, blank=True)
    operator = models.CharField(max_length=1, default="-", choices=OPERATOR_CHOISES)

    def __str__(self) -> str:
        if self.concept:
            return f"{self.concept.name} - {self.concept_amount}"
        return f"{self.payroll} - {self.payroll_entry}"

    def __repr__(self):
        return "{}"

    def get_concept_name(self) -> str:
        try:
            return self.concept.name
        except AttributeError:
            return ""

    def get_meployee_name(self):
        return self.payroll_entry.user.full_name()

    get_meployee_name.short_description = "Nombre empelado"

    class Meta:
        db_table = "PAYROLL_PAYMENT_DETAIL"
        verbose_name = "Detalle de pago"
        verbose_name_plural = "Detalles de Pagos de nómina"
