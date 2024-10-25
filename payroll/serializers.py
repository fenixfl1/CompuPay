from django.forms import model_to_dict
from django.db.models import Q
from rest_framework import serializers
from helpers.serializers import BaseModelSerializer
from payroll.models import (
    Adjustment,
    DeductionXuser,
    Deductions,
    Payroll,
    PayrollEntry,
    PayrollPaymentDetail,
    PayrollSettings,
)


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
    desc_type = serializers.SerializerMethodField()
    user = serializers.CharField(source="payroll_entry.user.full_name")
    username = serializers.CharField(source="payroll_entry.user.username")
    payroll_id = serializers.CharField(source="payroll_entry.payroll_id")
    avatar = serializers.CharField(source="payroll_entry.user.get_avatar")
    desc_state = serializers.SerializerMethodField()

    def get_desc_state(self, instance: Adjustment):
        values = dict(Adjustment.STATE_CHOICES)
        return values.get(instance.state, None)

    def get_desc_type(self, instance: Adjustment):
        return "Descuento" if instance.type == "D" else "Bono"

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
        entries = PayrollEntry.objects.filter(payroll=instance)

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
