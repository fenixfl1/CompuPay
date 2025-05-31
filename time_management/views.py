from django.forms import model_to_dict
from rest_framework.request import Request
from rest_framework.response import Response

from helpers.common import BaseProtectedViewSet
from helpers.exceptions import PayloadValidationError, viewException
from helpers.serializers import DynamicSerializer, PaginationSerializer
from helpers.utils import (
    advanced_query_filter,
    dict_key_to_lower,
    list_values_to_lower,
    time_to_decimal,
)
from payroll.models import Concept
from time_management.models import Leaves, Overtime
from time_management.serializars import LeaveSerializer, OvertimeSerializer
from users.models import User


class LeavesViewSet(BaseProtectedViewSet):

    @viewException
    def create_leave(self, request: Request):
        data = dict_key_to_lower(request.data)

        if not data:
            raise PayloadValidationError("The body request is empty.")

        username = data.get("employee", None)
        employee = User.objects.get(username=username)
        if not employee:
            raise PayloadValidationError(f"El empleado @{username} no encontrado")

        concept_id = data.pop("concept_id", None)
        if not concept_id:
            raise PayloadValidationError("CONCEPT_ID is required.")

        concept = Concept.objects.get(concept_id=concept_id)
        if not concept:
            raise PayloadValidationError(f"concept with id '{concept_id}' not found.")

        data["employee"] = employee
        data["state"] = "A"
        data["concept"] = concept

        Leaves.create(request, **data)

        return Response({"message": "Registro completado exitosamente."})

    @viewException
    def update_leave(self, request: Request):
        data = dict_key_to_lower(request.data)

        leave_id = data.get("leave_id", None)
        if not leave_id:
            raise PayloadValidationError("LEAVE_ID is requerido")

        leave = Leaves.objects.get(leave_id=leave_id)
        if not leave:
            raise PayloadValidationError("Registro no encontrado")

        Leaves.update(request, leave, **data)

        return Response({"message": "Registro actualizado con exito"})

    @viewException
    def get_leaves(self, request: Request):
        conditions = request.data.get("condition", None)
        fields = list_values_to_lower(request.data.get("fields", None))

        if not conditions:
            raise PayloadValidationError("CONDIITON es requerido")
        if not isinstance(conditions, list):
            raise PayloadValidationError("Invalid condition")

        condition, excludes = advanced_query_filter(conditions)

        leaves = Leaves.objects.filter(condition)

        for exclude in excludes:
            leaves = leaves.exclude(**exclude)

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(leaves.distinct(), request)

        serializer = []
        if fields:
            if not isinstance(fields, list):
                raise PayloadValidationError("Invalid format for field 'FIELDS'")
            serializer = DynamicSerializer(
                model=Leaves, fields=fields, instance=page, many=True
            )
        else:
            serializer = LeaveSerializer(page, many=True, context={"request": request})

        return paginator.get_paginated_response(serializer.data)

    @viewException
    def get_leave(self, _request: Request, leave_id: int):

        leave = Leaves.objects.get(leave_id=leave_id)
        if not leave:
            raise PayloadValidationError(
                f"No se encontró ningún registro con el id: '{leave_id}'"
            )

        serializer = LeaveSerializer(leave, data=model_to_dict(leave))
        serializer.is_valid(raise_exception=True)

        return Response({"data": serializer.data})


class OvertimeViewSet(BaseProtectedViewSet):

    @viewException
    def create_overtime(self, request: Request):
        data = dict_key_to_lower(request.data)

        if not data:
            raise PayloadValidationError("The request body is empty.")

        username = data.get("employee", None)
        if not username:
            raise PayloadValidationError("employee is required.")

        employee = User.objects.get(username=username)
        if not employee:
            raise PayloadValidationError(f"Employee '@{username}' not found.")

        concept_id = data.pop("concept_id", None)
        if not concept_id:
            raise PayloadValidationError("CONCEPT_ID is required.")

        concept = Concept.objects.get(concept_id=concept_id)
        if not concept:
            raise PayloadValidationError("Any concept found with the given concept_id.")

        data["employee"] = employee
        data["hours"] = time_to_decimal(data.get("hours"))
        data["concept"] = concept

        Overtime.create(request, **data)

        return Response({"message": "Horas extras registradas exitosamente."})

    @viewException
    def update_overtime(self, request: Request):
        data = dict_key_to_lower(request.data)

        if not data:
            raise PayloadValidationError("The request body is empty.")

        overtime_id: int = data.get("overtime_id", None)
        overtime = Overtime.objects.get(overtime_id=overtime_id)
        if not overtime:
            raise PayloadValidationError(
                f'Any data found with the given overtime_id "{overtime_id}".'
            )

        if data.get("hours", None) is not None:
            data["hours"] = time_to_decimal(data.get("hours"))

        Overtime.update(request, overtime, **data)

        return Response({"message": "Registro actualizado con éxito."})

    @viewException
    def get_overtimes(self, request: Request):
        conditions = request.data.get("condition", None)
        fields = request.data.get("fields", None)

        if not conditions:
            raise PayloadValidationError("The condition is required.")

        condition, excludes = advanced_query_filter(conditions)

        overtimes = Overtime.objects.filter(condition)

        for exclude in excludes:
            overtimes = overtimes.exclude(**exclude)

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(overtimes.distinct(), request)

        if fields:
            if not isinstance(fields, list):
                raise PayloadValidationError("Invalid format for field 'FIELDS'")
            serializer = DynamicSerializer(
                model=Overtime, fields=fields, instance=page, many=True
            )
        else:
            serializer = OvertimeSerializer(
                page, many=True, context={"request": request}
            )

        return paginator.get_paginated_response(serializer.data)

    @viewException
    def get_overtime(self, _request: Request, overtime_id: str):
        overtime = Overtime.objects.get(overtime_id=overtime_id)

        if not overtime:
            raise PayloadValidationError(
                f"No se encontró ningún registro con el id: '{overtime_id}'"
            )

        print("*" * 75)
        print(f"{model_to_dict(overtime)}")
        print("*" * 75)

        serializer = OvertimeSerializer(overtime, data=model_to_dict(overtime))
        serializer.is_valid(raise_exception=True)

        return Response({"data": serializer.data})
