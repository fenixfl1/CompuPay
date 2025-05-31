from decimal import Decimal, getcontext
from django.forms import model_to_dict
from django.db.models import Q
from rest_framework import serializers
from helpers.serializers import BaseModelSerializer, BaseReportModelSerializer
from helpers.utils import currency_format
from payroll.models import (
    Adjustment,
    DeductionXuser,
    Deductions,
    Payroll,
    PayrollEntry,
    PayrollPaymentDetail,
    PayrollSettings,
)
from time_management.models import Overtime


getcontext().prec = 2


class PayrollInfoSerializer(BaseModelSerializer):
    label = serializers.SerializerMethodField()
    payroll_config = serializers.SerializerMethodField()
    current_period = serializers.SerializerMethodField()

    def get_current_period(self, instance: Payroll):
        return instance.period

    def get_payroll_config(self, instance: Payroll):
        config = instance.get_config()
        serializer = PayrollSettingSerializer(config, data=model_to_dict(config))
        serializer.is_valid(raise_exception=True)
        return serializer.data

    def get_label(self, instance: Payroll):
        return str(instance)

    class Meta:
        model = Payroll
        fields = (
            "payroll_id",
            "label",
            "next_payment",
            "current_period",
            "payroll_config",
            "includes_overtime",
            "includes_leaves",
        )


class PayrollSettingSerializer(BaseModelSerializer):
    desc_period = serializers.SerializerMethodField()

    def get_desc_period(self, instance: PayrollSettings):
        return dict(PayrollSettings.DEDUCTION_PERIOD_CHOICES).get(instance.periods)

    class Meta:
        model = PayrollSettings
        fields = "__all__"


class PayrollSerializer(BaseModelSerializer):
    entries = serializers.SerializerMethodField()

    def get_entries(self, instance: Payroll):
        entries = PayrollEntry.objects.filter(payroll=instance)
        return PayrollEntrySerializer(entries, many=True).data

    class Meta:
        model = Payroll
        fields = "__all__"


class PayrollEntrySerializer(BaseModelSerializer):
    full_name = serializers.CharField(source="user.full_name")
    currency = serializers.CharField(source="user.currency")
    salary = serializers.CharField(source="user.salary")
    desc_status = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    bonus = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    isr = serializers.SerializerMethodField()
    afp = serializers.SerializerMethodField()
    sfs = serializers.SerializerMethodField()
    overtimes = serializers.SerializerMethodField()
    vacations = serializers.SerializerMethodField()
    other_discount = serializers.SerializerMethodField()
    net_salary = serializers.SerializerMethodField()

    def get_net_salary(self, instance: PayrollEntry):
        user = instance.user
        payroll = instance.payroll

        # Salario base proporcional al período
        base_salary = (user.salary or 0) / (payroll.get_config().periods or 1)

        # Configuración de inclusión
        include_overtime = getattr(payroll, "includes_overtime", True)
        include_leaves = getattr(payroll, "includes_leaves", True)
        show_withholding = getattr(payroll, "show_withholding", True)

        # Componentes del salario
        bonus = self.get_bonus(instance) or 0
        overtime = self.get_overtimes(instance) if include_overtime else 0
        vacations = self.get_vacations(instance) if include_leaves else 0

        # Descuentos
        discount = self.get_discount(instance) or 0
        other_discount = self.get_other_discount(instance) if include_leaves else 0

        isr = self.get_isr(instance) if show_withholding else 0
        afp = self.get_afp(instance) if show_withholding else 0
        sfs = self.get_sfs(instance) if show_withholding else 0

        net_salary = (
            base_salary
            + overtime
            + vacations
            + bonus
            - discount
            - other_discount
            - isr
            - afp
            - sfs
        )

        return round(net_salary, 2)

    def get_vacations(self, instance: PayrollEntry):
        vacations = instance.get_leaves().values_list("amount", flat=True)
        return sum(vacations)

    def get_other_discount(self, instance: PayrollEntry):
        discounts = instance.get_leaves(False).values_list("amount", flat=True)
        return sum(discounts)

    def get_overtimes(self, instance: PayrollEntry):
        overtimes = instance.get_employee_overtime().values_list("rate", "hours")
        total = sum(rate * hours for rate, hours in overtimes)
        return total

    def get_avatar(self, instance: PayrollEntry):
        return instance.user.get_avatar()

    def get_desc_status(self, instance: PayrollEntry):
        return instance.get_status()

    def get_isr(self, instance: PayrollEntry):
        return DeductionXuser.get_isr(instance.user)

    def get_afp(self, instance: PayrollEntry):
        return DeductionXuser.get_afp(instance.user)

    def get_sfs(self, instance: PayrollEntry):
        return DeductionXuser.get_sfs(instance.user)

    def get_bonus(self, instance: PayrollEntry):
        return Adjustment.calc_bonus(instance)

    def get_discount(self, instance: PayrollEntry):
        return Adjustment.calc_deduction(instance)

    class Meta:
        model = PayrollEntry
        fields = "__all__"


class AdjustmentSerializer(BaseModelSerializer):
    desc_concept = serializers.CharField(source="concept.name")
    user = serializers.CharField(source="payroll_entry.user.full_name")
    username = serializers.CharField(source="payroll_entry.user.username")
    payroll_id = serializers.CharField(source="payroll_entry.payroll_id")
    avatar = serializers.CharField(source="payroll_entry.user.get_avatar")
    desc_state = serializers.SerializerMethodField()

    def get_desc_state(self, instance: Adjustment):
        values = dict(Adjustment.STATE_CHOICES)
        return values.get(instance.state, None)

    class Meta:
        model = Adjustment
        fields = "__all__"


class DeductionSerializer(BaseModelSerializer):
    label = serializers.SerializerMethodField()

    def get_label(self, instance: Deductions):
        labels = dict(Deductions.ADJUSTMENT_TYPE)
        return f"{labels[instance.name]} (%{instance.percentage})"

    class Meta:
        model = Deductions
        fields = "__all__"


class PayrollHistorySerializer(BaseModelSerializer):
    label = serializers.SerializerMethodField()
    period = serializers.SerializerMethodField()
    entries = serializers.SerializerMethodField()
    desc_state = serializers.SerializerMethodField()

    def get_desc_state(self, instance: Payroll):
        labels = dict(Payroll.STATUS_CHOICES)
        return labels[instance.status]

    def get_entries(self, instance: Payroll):
        entries = PayrollEntry.objects.filter(
            payroll=instance, state=PayrollEntry.ACTIVE
        )

        serializer = PayrollEntryWithDetailSerializer(entries, many=True)
        return serializer.data

    def get_period(self, instance: Payroll):
        return instance.period

    def get_label(self, instance: Payroll):
        return str(instance)

    class Meta:
        model = Payroll
        fields = "__all__"


class PayrollEntryWithDetailSerializer(PayrollEntrySerializer):
    payment_details = serializers.SerializerMethodField()

    def get_payment_details(self, instance: PayrollEntry):
        details = PayrollPaymentDetail.objects.filter(
            Q(payroll_entry=instance) & Q(state=PayrollPaymentDetail.ACTIVE)
        )
        serializer = PayrollPaymentDetailSerializer(details, many=True)
        return serializer.data

    class Meta:
        model = PayrollEntry
        fields = "__all__"


class PayrollPaymentDetailSerializer(BaseModelSerializer):
    desc_concept = serializers.CharField(source="get_concept_name")

    class Meta:
        model = PayrollPaymentDetail
        fields = "__all__"


class PayrollEntryReportSerializer(BaseReportModelSerializer):
    id = serializers.CharField(source="payroll_entry_id")
    nombre = serializers.CharField(source="user.full_name")
    salario = serializers.SerializerMethodField()
    estado = serializers.SerializerMethodField()
    bonos = serializers.SerializerMethodField()
    descuentos = serializers.SerializerMethodField()
    isr = serializers.SerializerMethodField()
    afp = serializers.SerializerMethodField()
    sfs = serializers.SerializerMethodField()
    horas_extras = serializers.SerializerMethodField()
    vacaciones = serializers.SerializerMethodField()

    def get_salario(self, instance: PayrollEntry):
        return currency_format(instance.user.salary)

    def get_vacaciones(self, instance: PayrollEntry):
        vacations = instance.get_leaves().values_list("amount", flat=True)
        return currency_format(sum(vacations))

    def get_otros_descuentos(self, instance: PayrollEntry):
        discounts = instance.get_leaves(False).values_list("amount", flat=True)
        return sum(discounts)

    def get_horas_extras(self, instance: PayrollEntry):
        overtimes = instance.get_employee_overtime().values_list("rate", "hours")
        total = sum(rate * hours for rate, hours in overtimes)
        return currency_format(total)

    def get_estado(self, instance: PayrollEntry):
        return instance.get_status()

    def get_isr(self, instance: PayrollEntry):
        return currency_format(DeductionXuser.get_isr(instance.user))

    def get_afp(self, instance: PayrollEntry):
        return currency_format(DeductionXuser.get_afp(instance.user))

    def get_sfs(self, instance: PayrollEntry):
        amount = DeductionXuser.get_sfs(instance.user)
        return currency_format(amount)

    def get_bonos(self, instance: PayrollEntry):
        bonus = Adjustment.calc_bonus(instance)
        return currency_format(bonus)

    def get_descuentos(self, instance: PayrollEntry):
        discounts = Adjustment.calc_deduction(instance)
        others = self.get_otros_descuentos(instance)
        return currency_format(discounts + others)

    class Meta:
        model = PayrollEntry
        fields = (
            "id",
            "nombre",
            "salario",
            "bonos",
            "horas_extras",
            "vacaciones",
            "descuentos",
            "isr",
            "afp",
            "sfs",
            "estado",
        )


class PayrollPaymentReportSerializer(BaseReportModelSerializer):
    id = serializers.CharField(source="payroll_entry_id")
    estado = serializers.CharField(source="get_status")
    details = serializers.SerializerMethodField()
    empleado = serializers.SerializerMethodField()
    sueldo_bruto = serializers.SerializerMethodField()

    def get_sueldo_bruto(self, instance: PayrollEntry):
        total = instance.user.salary / instance.payroll.get_config().periods
        return currency_format(total)

    def get_empleado(self, instance: PayrollEntry):
        return repr(instance.user)

    def get_details(self, instance: PayrollEntry):
        obj = {}
        details = PayrollPaymentDetail.objects.filter(payroll_entry=instance)
        for detail in details:
            obj[detail.concept.name] = (
                f"{detail.comment or '' } {currency_format(detail.concept_amount)}"
            )
        return obj

    class Meta:
        model = PayrollEntry
        fields = (
            "id",
            "empleado",
            "estado",
            "sueldo_bruto",
            "details",
        )
