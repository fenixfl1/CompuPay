import locale
import datetime
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
from helpers.utils import ordinal
from users.models import User


locale.setlocale(locale.LC_TIME, "Spanish_Spain.1252")

getcontext().prec = 2


class Payroll(BaseModels):
    """
    Payroll model\n
    `TABLE_NAME`: PAYROLL
    """

    STATUS_CHOICES = (("P", "Pendiente"), ("F", "Finalzada"))
    PENDING = "P"
    DONE = "F"

    payroll_id = models.AutoField(primary_key=True)
    period_start = models.DateField()
    period_end = models.DateField()
    period = models.IntegerField(default=1, unique_for_month=True)
    status = models.CharField(
        blank=True, null=True, choices=STATUS_CHOICES, default=PENDING
    )

    REQUIRED_FIELDS = ["period_start", "period_end", "state"]
    ALLOWED_FIELDS = REQUIRED_FIELDS + ["payroll_id", "employees"]

    def __str__(self):
        config = self.get_config()
        # pylint: disable=no-member
        month = self.period_start.strftime("%B")
        if config.periods == 1:
            return f"Nómina de {month}"
        return f"{ordinal(self.period)} nómina de {month}"

    def next_payment(self) -> str:
        # pylint: disable=no-member
        return f'{self.period_end.strftime("%A %d de %B")}'

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
            raise ValidationError("No se encontró una configuración de nómina acitva")

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

    @classmethod
    def autostart_payroll(cls, user: User):
        try:
            config = (
                PayrollSettings.objects.filter(
                    Q(state=PayrollSettings.ACTIVE) & Q(autopay=True)
                )
                .order_by("-created_at")
                .first()
            )

            if not config:
                raise APIException("No hay configuración activa para la nómina.")

            last_payroll = (
                Payroll.objects.filter(status=Payroll.DONE)
                .order_by("-period_end")
                .first()
            )

            if last_payroll:
                period_start = last_payroll.period_end + timedelta(days=1)
            else:
                period_start = timezone.now().date()

            # Calculando la fecha final
            if config.duration_days == 30:
                period_end = period_start + timedelta(days=29)
            else:
                period_end = period_start + timedelta(days=config.duration_days - 1)

            payroll = Payroll.objects.create(
                payroll_id=Payroll.objects.all().count() + 1,
                period_start=period_start,
                period_end=period_end,
                created_by=user,
                state="A",
                status=Payroll.PENDING,
            )

            # add all active employees to the new payroll
            employees = User.objects.filter(Q(state="A") & Q(is_staff=True))
            PayrollEntry.create_entries(payroll, employees, user)

            return payroll

        except Exception as e:
            raise APIException(str(e)) from e

    @transaction.atomic
    def process_payroll(
        self, request: Request, users_id: list[int] = None
    ) -> "Payroll":
        settings = self.get_config()
        payroll_entries = PayrollEntry.objects.filter(payroll_id=self.payroll_id)
        if users_id:
            payroll_entries = payroll_entries.filter(user__user_id__in=users_id)

        for entry in payroll_entries:
            if settings.periods == self.period:
                deduction_user = DeductionXuser.get_user_deductions(entry.user)

                if deduction_user:
                    for deduction in deduction_user:
                        detail = PayrollPaymentDetail(
                            payroll=entry.payroll,
                            payroll_entry=entry,
                            concept=deduction.deduction.concept,
                            period=self.period,
                            concept_amount=DeductionXuser.get_deduction_amount(
                                entry.user, deduction.deduction.name
                            ),
                            state=PayrollPaymentDetail.ACTIVE,
                            created_by=request.user,
                            gross_salary=entry.user.salary,
                            comment=f"Descuento mensual por concepto de {deduction.deduction.name}",
                        )
                        detail.save()

            adjustments = Adjustment.get_by_entry(entry)
            if adjustments:
                for adjustment in adjustments:
                    operator = "+" if adjustment.type == "B" else "-"
                    detail = PayrollPaymentDetail(
                        payroll=entry.payroll,
                        payroll_entry=entry,
                        concept=adjustment.concept,
                        period=self.period,
                        concept_amount=Adjustment.get_amount(entry, adjustment.type),
                        state=PayrollPaymentDetail.ACTIVE,
                        created_by=request.user,
                        gross_salary=entry.user.salary,
                        comment=adjustment.description,
                        operator=operator,
                    )
                    detail.save()
                    Adjustment.objects.update(state=Adjustment.COMPLETED)

            discount = Adjustment.calc_deduction(entry)
            bonus = Adjustment.calc_bonus(entry)
            afp = DeductionXuser.get_afp(entry.user)
            sfs = DeductionXuser.get_sfs(entry.user)
            isr = DeductionXuser.get_isr(entry.user)

            salary = entry.user.salary / settings.periods
            net_salary = (salary + bonus) - discount - afp - sfs - isr

            detail = PayrollPaymentDetail(
                payroll=entry.payroll,
                payroll_entry=entry,
                concept=Concept.objects.get(name="SALARIO"),
                period=self.period,
                concept_amount=net_salary,
                state=PayrollPaymentDetail.ACTIVE,
                created_by=request.user,
                gross_salary=entry.user.salary,
                operator="+",
            )
            detail.save()

            payroll_entries.update(status=True)

    def save(self, *args, **kwargs):
        self.clean()  # Llama a clean antes de guardar
        super().save(*args, **kwargs)

    class Meta:
        db_table = "PAYROLL"
        verbose_name = "Nómina"
        verbose_name_plural = "Nóminas"
        ordering = ["-period_start"]


class Concept(BaseModels):
    """
    This model represents the concepts for each payroll entry payment.\n
    Each kind of discount or deduction have an concept: Example bonus, discount, text, etc..\n
    `TABLE_NAME` CONCEPTS
    """

    concept_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=20, null=False, blank=False, unique=False)
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

    PERIOD_CHOISES = ((1, "Mensual"), (2, "Quincenal"), (4, "Semanal"))
    DEDUCTION_PERIOD_CHOICES = (
        (1, "Primero"),
        (2, "Segundo"),
        (2, "Tercero"),
        (4, "Cuarto"),
    )

    periods = models.IntegerField(default=1, choices=PERIOD_CHOISES)
    autopay = models.BooleanField(default=False)
    deduction_period = models.IntegerField(
        default=2,
        choices=DEDUCTION_PERIOD_CHOICES,
        help_text="Período en el que se deben hacer los descuentos de ley",
    )

    def __str__(self):
        return f"Configuración Nómina - {self.pk}"

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

    @classmethod
    def create_entries(
        cls, payroll: Payroll, employees: list[User], currentuser: User
    ) -> list["PayrollEntry"]:
        try:
            enries: list[PayrollEntry] = []
            counter = cls.objects.all().count()
            for employee in employees:
                counter += 1
                enries.append(
                    PayrollEntry(
                        payroll_entry_id=counter,
                        payroll=payroll,
                        user=employee,
                        state="A",
                        created_by=currentuser,
                    )
                )
            cls.objects.bulk_create(enries)
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

    COMPLETED = "S"
    STATE_CHOICES = (("A", "Activo"), ("I", "Inactivo"), ("S", "Saldada"))
    ADJUSTMENT_TYPE = [
        ("B", "Bono"),
        ("D", "Descuento"),
    ]

    state = models.CharField(
        default="A", max_length=1, null=False, choices=STATE_CHOICES
    )
    adjustment_id = models.AutoField(primary_key=True)
    type = models.CharField(max_length=50, choices=ADJUSTMENT_TYPE)
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
            & Q(type="B")
            & Q(state=Adjustment.ACTIVE)
        )

        total_bonus = Decimal("0.0")
        for bonu in bonus:
            total_bonus += bonu.amount
        return total_bonus

    @classmethod
    def calc_deduction(cls, entry: PayrollEntry) -> Decimal:
        deduction = Adjustment.objects.filter(Q(payroll_entry=entry) & Q(type="D"))
        total_deduction = Decimal("0.0")
        for deduc in deduction:
            total_deduction += deduc.amount
        return total_deduction

    @classmethod
    def get_amount(cls, entry: PayrollEntry, _type: str) -> Decimal:
        deduction = Adjustment.objects.filter(Q(payroll_entry=entry) & Q(type=_type))
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
    def add_deductions_to_user(cls, deductions: list["Deductions"], user: User):
        user_deductions = []
        max_id = DeductionXuser.objects.all().aggregate(Max("id"))["id__max"]
        for deduction in deductions:
            max_id += 1
            user_deductions.append(
                DeductionXuser(
                    id=max_id,
                    state=Deductions.ACTIVE,
                    user=user,
                    deduction=Deductions.objects.get(deduction_id=deduction),
                    created_by=user.created_by,
                    created_at=datetime.datetime.now(),
                )
            )
        DeductionXuser.objects.bulk_create(user_deductions)

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
            percentage = deduction.percentage
            return (user.salary * percentage) / 100
        return Decimal("0.0")

    @classmethod
    def get_sfs(cls, user: User) -> Decimal:
        user_deduction = DeductionXuser.get_user_deductions(user, "SFS")
        if user_deduction:
            deduction = Deductions.objects.filter(
                Q(name="SFS")
                & Q(state=Deductions.ACTIVE)
                & Q(deduction_id=user_deduction.deduction.deduction_id)
            ).first()
            percentage = deduction.percentage
            return (user.salary * percentage) / 100
        return Decimal("0.0")

    @classmethod
    def get_isr(cls, user: User) -> Decimal:
        # Obtén la deducción ISR desde la base de datos
        user_deduction = DeductionXuser.get_user_deductions(user, "ISR")
        if user_deduction:
            deduction = Deductions.objects.filter(
                Q(name="ISR")
                & Q(state=Deductions.ACTIVE)
                & Q(deduction_id=user_deduction.deduction.deduction_id)
            ).first()

            # Porcentaje específico del usuario
            percentage = deduction.percentage / 100

            # Calcula las deducciones de AFP y SFS
            afp = DeductionXuser.get_afp(user)
            sfs = DeductionXuser.get_sfs(user)

            # Resta AFP y SFS del salario bruto
            tss = afp + sfs
            salary = user.salary - tss

            # Calcula el salario neto anual
            annual_net_salary = salary * 12

            # Aplica el porcentaje correspondiente para calcular el ISR mensual
            isr = (annual_net_salary * percentage) / 12

            return isr
        return Decimal("0.0")

    @classmethod
    def get_deduction_amount(cls, user: User, name: str):
        user_deduction = DeductionXuser.get_user_deductions(user, name)
        if user_deduction:
            deduction = Deductions.objects.filter(
                Q(name=name)
                & Q(state=Deductions.ACTIVE)
                & Q(deduction_id=user_deduction.deduction.deduction_id)
            ).first()
            percentage = deduction.percentage
            return (user.salary * percentage) / 100
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

    def get_concept_name(self) -> str:
        return self.concept.name

    def get_meployee_name(self):
        return self.payroll_entry.user.full_name()

    get_meployee_name.short_description = "Nombre empelado"

    class Meta:
        db_table = "PAYROLL_PAYMENT_DETAIL"
        verbose_name = "Detalle de pago"
        verbose_name_plural = "Detalles de Pagos de nómina"
