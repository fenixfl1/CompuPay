import random
from datetime import timedelta, datetime
from django.utils.timezone import now
from django.db.models import (
    Count,
    Sum,
    Avg,
    F,
    Q,
    ExpressionWrapper,
    DecimalField,
)
from django.db.models.functions import ExtractDay, TruncMonth, ExtractMonth
from rest_framework.request import Request
from rest_framework.response import Response

from dashboard.serializers import (
    ActivitySerializer,
    EmployeesByDepartmentSerializer,
    SalaryByDepartmentSerializer,
)
from helpers.common import BaseProtectedViewSet
from helpers.exceptions import PayloadValidationError, viewException
from helpers.serializers import PaginationSerializer
from helpers.statistics import UserStatistics
from helpers.utils import (
    advanced_query_filter,
    dict_key_to_lower,
)
from helpers.constants import colors
from payroll.models import PayrollPaymentDetail
from tasks.models import Task
from users.models import ActivityLog, Department, User


class DashboardViewSet(BaseProtectedViewSet):
    """
    View set for dashborad informatio
    """

    @viewException
    def get_recent_activities(self, request: Request):
        """
        `METHOD` POST
        """

        condition = request.data.get("condition", None)
        if not condition:
            raise PayloadValidationError("condition is requiered")

        conditions, exclude = advanced_query_filter(condition)

        activities = ActivityLog.objects.filter(conditions)

        for ex in exclude:
            activities = activities.exclude(**ex)

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(activities, request)

        serializer = ActivitySerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)

    @viewException
    def get_employees_by_department(self, _request: Request):
        """
        Return a list of employes grouped by department\n
        `METHOD` POST
        """
        departments = Department.objects.all()

        serializer = EmployeesByDepartmentSerializer(departments, many=True)

        return Response({"data": serializer.data})

    @viewException
    def task_performance(self, request: Request):
        """
        Vista para obtener el rendimiento de tareas agrupadas por departamento
        en un rango de fechas definido por el usuario.

        condition: {
            "start_date": "YYYY-MM-DD", (opcional, por defecto será el primer día del mes actual)
            "end_date": "YYYY-MM-DD", (opcional, por defecto será la fecha actual)
            "departments": [1, 2, 3] (opcional, lista de departamentos)
        }
        """
        condition = dict_key_to_lower(request.data.get("condition", None))
        if not condition:
            raise PayloadValidationError("condition is required")

        date_range: list[str] = condition.get("date_range", None)
        if date_range is None:
            raise PayloadValidationError("date_range is required")

        # Fechas de inicio y fin
        start_date = date_range[0]
        end_date = date_range[1]

        # Si las fechas son inválidas, lanzar una excepción
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise PayloadValidationError(
                "Invalid date format, expected 'YYYY-MM-DD'"
            ) from ValueError

        # Filtrar por departamentos si se especifican
        departments = condition.get("departments", None)

        # Anotación para extraer el día del campo created_at
        task_data = (
            Task.objects.filter(created_at__range=[start_date, end_date])
            .annotate(day=ExtractDay("created_at"))
            .values("day", "users__department__name")
            .annotate(task_count=Count("task_id"))
            .order_by("day", "users__department__name")
        )

        # Obtener todos los departamentos activos
        active_departments = Department.objects.filter(state=Department.ACTIVE)
        if departments and isinstance(departments, list):
            active_departments = active_departments.filter(
                department_id__in=departments
            )

        performance_data = []

        # Recorrer los días del rango de fechas
        for day in range((end_date - start_date).days + 1):
            current_day = start_date + timedelta(days=day)
            day_data = {"day": current_day.day}  # Usar el día numérico

            for department in active_departments.values_list("name", flat=True):
                day_data[department] = next(
                    (
                        item["task_count"]
                        for item in task_data
                        if item["day"] == current_day.day
                        and item["users__department__name"] == department
                    ),
                    0,
                )

            performance_data.append(day_data)

        return Response(
            {
                "data": {
                    "performance": performance_data,
                    "departments": active_departments.values("name", "color"),
                }
            }
        )

    @viewException
    def get_user_statistic(self, _request: Request):
        users = User.objects.filter(Q(state__in=[User.ACTIVE, User.INTERN]))

        line_chart_data = UserStatistics.get_employes_by_month()

        data = users.aggregate(
            total_registered=Count("user_id"),
            total_inters=Count("user_id", filter=Q(state=User.INTERN)),
            new_employees=Count(
                "user_id", filter=(Q(created_at__gte=now().replace(day=1)))
            ),
            total_employees=Count(
                "user_id",
                filter=(Q(state=User.ACTIVE) & Q(is_staff=True) & Q(salary__gt=0)),
            ),
        )

        data["line_chart"] = line_chart_data

        return Response({"data": data})

    @viewException
    def salary_by_department(self, _request: Request):
        """
        This endpoint is used to get a salary distribution by department
        """

        employees = User.get_employees()

        total_salary_all_departments = employees.aggregate(total_salary=Sum("salary"))[
            "total_salary"
        ]

        employees_by_department = (
            employees.values("department__name")
            .annotate(
                department_color=F("department__color"),
                total_salary=Sum("salary"),
                average_salary=Avg("salary"),
                percent=ExpressionWrapper(
                    Sum("salary") * 100.0 / total_salary_all_departments,
                    output_field=DecimalField(),
                ),
            )
            .order_by("department__name")
        )

        serializer = SalaryByDepartmentSerializer(employees_by_department, many=True)

        return Response({"data": serializer.data})

    @viewException
    def get_payroll_payment_detail(self, _request: Request):
        payroll_details = (
            PayrollPaymentDetail.objects.annotate(
                month=TruncMonth("payroll__period_end")
            )
            .values("month", "concept__name")
            .annotate(total_amount=Sum("concept_amount"))
            .order_by("month")
        )

        all_concepts = (
            PayrollPaymentDetail.objects.values("concept__name")
            .distinct()
            .order_by("concept__name")
        )

        concept_list = [concept["concept__name"] for concept in all_concepts]

        result = {}
        for detail in payroll_details:
            month = detail["month"].strftime("%B")
            concept_name = detail["concept__name"]
            total_amount = detail["total_amount"]

            if month not in result:
                result[month] = {"month": month}

            result[month][concept_name] = total_amount

        for month_data in result.values():
            for concept in concept_list:
                if concept not in month_data:
                    month_data[concept] = 0.0

        available_colors = colors.copy()
        random.shuffle(available_colors)

        concept_color_list = []
        for i, concept_name in enumerate(concept_list):
            if i >= len(available_colors):
                random_color = random.choice(colors)
            else:
                random_color = available_colors[i]

            concept_color_list.append({"concept": concept_name, "fill": random_color})

        return Response(
            {"data": {"data": list(result.values()), "concepts": concept_color_list}}
        )
