from rest_framework import serializers

from time_management.models import Leaves, Overtime
from helpers.utils import decimal_to_time
from helpers.serializers import BaseModelSerializer
from helpers.constants import months


class LeaveSerializer(BaseModelSerializer):
    desc_concept = serializers.SerializerMethodField()
    date_range = serializers.SerializerMethodField()
    concept_id = serializers.CharField(source="concept", required=False)

    def get_date_range(self, instance: Leaves | dict):
        try:
            if isinstance(instance, dict):
                return None
            start_day = instance.start_date.day
            start_month = months[instance.start_date.month]
            end_day = instance.end_date.day
            end_month = months[instance.end_date.month]

            return f"Del {start_day} de {start_month} al {end_day} de {end_month}"
        except IndexError:
            return ""

    def get_desc_concept(self, instance: Leaves):
        return instance.concept.name

    class Meta:
        model = Leaves
        fields = "__all__"


class OvertimeSerializer(BaseModelSerializer):
    time = serializers.SerializerMethodField(required=False)
    total = serializers.DecimalField(
        source="get_amount", decimal_places=2, max_digits=10, required=False
    )

    def get_time(self, instance: Overtime):
        return decimal_to_time(instance.hours)

    class Meta:
        model = Overtime
        fields = "__all__"
