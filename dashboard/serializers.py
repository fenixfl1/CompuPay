from django.db.models import Q
from rest_framework import serializers

from helpers.utils import get_month_day_name
from tasks.models import Task
from users.models import ActivityLog, Department, User
from helpers.serializers import BaseModelSerializer, BaseSerializer


class ActivitySerializer(BaseModelSerializer):
    desc_action_flag = serializers.SerializerMethodField()
    verbose_name = serializers.SerializerMethodField()

    def get_verbose_name(self, instance: ActivityLog):
        model_class = instance.content_type.model_class()
        return model_class._meta.verbose_name_plural

    def get_desc_action_flag(self, instance: ActivityLog):
        values = dict(ActivityLog.ACTION_CHOICES)
        return values[instance.action_flag]

    class Meta:
        model = ActivityLog
        fields = "__all__"


class EmployeesByDepartmentSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="__str__")
    value = serializers.IntegerField(source="get_employees_count")
    fill = serializers.CharField(source="color")

    class Meta:
        model = Department
        fields = ("name", "value", "fill")


class EmployeesPerformanceSerialezer(serializers.ModelSerializer):
    deparments = serializers.SerializerMethodField()


class TaskPermanceSerilizer(BaseSerializer):
    departments = serializers.SerializerMethodField()

    def get_departments(self, _obj):
        return []

    def to_representation(self, instance):
        super().to_representation(instance)

        period = self.context.get("period")
        period_value: list[int] = self.context.get("period_value")
        result = {}

        for item in period_value:
            departmane_name = instance["users__department__name"]
            task_count = instance["task_count"]
            result[departmane_name] = task_count
            result["name"] = get_month_day_name(item, period)

        return result


class UserStatisticsSerializer(BaseSerializer):
    registered_this_month = serializers.SerializerMethodField()
    total_employees = serializers.SerializerMethodField()
    total_active_users = serializers.SerializerMethodField()
    total_applicants = serializers.IntegerField()

    def get_registered_this_month(self, obj):
        return obj["registered_this_month"]

    def get_total_employees(self, obj):
        return obj["total_employees"]

    def get_total_active_users(self, obj):
        return obj["total_active_users"]

    def to_representation(self, instance) -> dict:
        """
        Convierte recursivamente las claves de los diccionarios a mayúsculas
        """

        def uppercase_keys(data):
            if isinstance(data, dict):
                return {k.upper(): uppercase_keys(v) for k, v in data.items()}
            return data

        # Obtener la representación original
        to_repr = super().to_representation(instance)

        # Convertir las claves y las claves internas a mayúsculas
        result = uppercase_keys(to_repr)

        return result


class SalaryByDepartmentSerializer(BaseSerializer):
    fill = serializers.CharField(source="department_color")
    department = serializers.CharField(source="department__name")
    uv = serializers.DecimalField(
        source="total_salary", decimal_places=2, max_digits=10
    )
    pv = serializers.DecimalField(
        source="average_salary", decimal_places=2, max_digits=10
    )
    percentage = serializers.DecimalField(
        source="percent", decimal_places=2, max_digits=10
    )
