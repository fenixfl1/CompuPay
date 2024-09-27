import datetime
import pandas as pd
from django.utils import timezone
from django.db.models import (
    Sum,
    F,
    Avg,
    DecimalField,
    ExpressionWrapper,
    Count,
)
from django.db.models.functions import TruncMonth
from django.contrib.auth import get_user_model

from users.models import UserManager


User = get_user_model()


class UserStatistics:

    @staticmethod
    def get_user_statistics():
        # Obtener todos los usuarios
        users = User.objects.all().values(
            "created_at", "is_staff", "state", "updated_at"
        )

        # Convertir los datos de usuarios a un DataFrame de Pandas
        df = pd.DataFrame(list(users))

        # Verificar que los datos se cargaron correctamente
        print(df.head())

        # Fecha actual
        now = timezone.now()
        current_month = now.month
        current_year = now.year

        # Filtrar por mes actual
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["updated_at"] = pd.to_datetime(df["updated_at"])
        df["month"] = df["created_at"].dt.month
        df["year"] = df["created_at"].dt.year

        # Filtrar por mes anterior
        first_day_of_current_month = now.replace(day=1)
        last_day_of_previous_month = first_day_of_current_month - datetime.timedelta(
            days=1
        )
        previous_month = last_day_of_previous_month.month
        previous_year = last_day_of_previous_month.year

        # Usuarios registrados este mes
        registered_this_month = df[
            (df["month"] == current_month) & (df["year"] == current_year)
        ].shape[0]

        # Usuarios registrados el mes pasado
        registered_last_month = df[
            (df["month"] == previous_month) & (df["year"] == previous_year)
        ].shape[0]

        # Calcular crecimiento en registros de usuarios
        registered_change = (
            (registered_this_month - registered_last_month)
            / registered_last_month
            * 100
            if registered_last_month != 0
            else 0
        )

        # Empleados activos
        total_employees = df[(df["is_staff"] is True) & (df["state"] == "A")].shape[0]

        # Empleados activos el mes pasado
        total_employees_last_month = df[
            (df["is_staff"] is True)
            & (df["state"] == "A")
            & (df["updated_at"].dt.month == previous_month)
            & (df["updated_at"].dt.year == previous_year)
        ].shape[0]

        # Crecimiento de empleados activos
        employees_change = (
            (total_employees - total_employees_last_month)
            / total_employees_last_month
            * 100
            if total_employees_last_month != 0
            else 0
        )

        # Registros activos
        total_active_users = df[df["state"] == "A"].shape[0]

        # Registros activos el mes pasado
        total_active_users_last_month = df[
            (df["state"] == "A")
            & (df["updated_at"].dt.month == previous_month)
            & (df["updated_at"].dt.year == previous_year)
        ].shape[0]

        # Crecimiento de registros activos
        active_users_change = (
            (total_active_users - total_active_users_last_month)
            / total_active_users_last_month
            * 100
            if total_active_users_last_month != 0
            else 0
        )

        # Postulantes (state = 'P' y is_staff = True)
        total_applicants = df[(df["is_staff"] is True) & (df["state"] == "P")].shape[0]

        # Retornar los resultados
        return {
            "registered_this_month": {
                "total": registered_this_month,
                "growth": round(registered_change, 2),
            },
            "total_employees": {
                "total": total_employees,
                "growth": round(employees_change, 2),
            },
            "total_active_users": {
                "total": total_active_users,
                "growth": round(active_users_change, 2),
            },
            "total_applicants": total_applicants,
        }

    @staticmethod
    def salary_by_department():
        """
        This endpoint is used to get a salary distribution by department
        """

        employees: UserManager = User.get_employees()
        employees = employees.annotate(
            department_color=F("department__color"),
            dept_name=F("department__name"),
        )

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

        return employees_by_department

    @staticmethod
    def get_employes_by_month() -> list[dict]:
        employees = User.objects.filter(state=User.ACTIVE)

        employees_by_month = (
            employees.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(value=Count("user_id"))
            .order_by("month")
        )

        result = [
            {
                "month": employee["month"].strftime("%B").capitalize(),
                "value": employee["value"],
            }
            for employee in employees_by_month
        ]

        return result
