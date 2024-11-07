import datetime
from django.forms import model_to_dict
from django.db.models import Q
from django.contrib.auth import get_user_model

from rest_framework.request import Request
from rest_framework.exceptions import APIException, NotFound
from rest_framework.response import Response

from helpers.common import BaseProtectedViewSet
from helpers.constants import PAYLOAD_VALIDATION_ERROR
from helpers.exceptions import PayloadValidationError, viewException
from helpers.serializers import PaginationSerializer
from helpers.utils import (
    advanced_query_filter,
    dict_key_to_lower,
    simple_query_filter,
)
from payroll.models import Adjustment, Concept, Deductions, Payroll, PayrollEntry
from payroll.serializers import (
    AdjustmentSerializer,
    DeductionSerializer,
    PayrollEntrySerializer,
    PayrollHistorySerializer,
    PayrollInfoSerializer,
    PayrollSerializer,
)
from users.models import ActivityLog


User = get_user_model()


class PayrollViewSet(BaseProtectedViewSet):
    """
    Payroll view set. This view set allows to manage the following actions:
    - `POST` Create a payroll
    - `PUT` Update a payroll
    - `POST` Get a list of payrolls
    - `POST` Get a payroll
    - `POST` Get a list of payroll entries
    - `POST` Create a payroll entry
    - `PUT` Update a payroll entry
    """

    @viewException
    def create_payroll(self, request: Request):
        """
        Create a payroll
        """
        data = dict_key_to_lower(request.data)

        for field in Payroll.REQUIRED_FIELDS:
            if not data.get(field):
                raise PayloadValidationError(
                    f"{field.upper()} is required",
                )

        for field in data.keys():
            if field not in Payroll.ALLOWED_FIELDS:
                raise PayloadValidationError(f"{field} is not allowed")

        if Payroll.objects.filter(status=Payroll.PENDING).exists():
            raise APIException(
                "Ya tiene una nómina pendiente, no puede iniciar una nueva."
            )

        employees = data.pop("employees")
        payroll = Payroll(**data)
        data["employees"] = employees
        payroll = payroll.create_payroll(request, **data)

        try:
            ActivityLog.register_activity(
                instance=payroll,
                user=request.user,
                action=1,
                message=f"{request.user.username} regisro la {str(payroll)}",
            )
        except AttributeError:
            pass

        return Response({"message": "Nomina registrada exitosamente"})

    @viewException
    def update_payroll(self, request: Request):
        """
        Update a payroll
        """
        data = dict_key_to_lower(request.data)

        for field in data.keys():
            if field in Payroll.NON_UPDATEABLE_FIELDS:
                raise PayloadValidationError(f"'{field}' is not allowed to be updated")
            if field not in Payroll.ALLOWED_FIELDS:
                raise PayloadValidationError(f"'{field}' is not allowed")

        payroll = Payroll.objects.get(payroll_id=data.get("payroll_id"))
        if not payroll:
            raise APIException(
                "Nomina no encontrada",
                code=PAYLOAD_VALIDATION_ERROR,
            )

        payroll = Payroll.update(request, payroll, **data)

        serializer = PayrollSerializer(
            payroll, data=model_to_dict(payroll), context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        ActivityLog.register_activity(
            instance=payroll,
            user=request.user,
            action=2,
            message=f"{request.user.username} acutualizo la {str(payroll)}",
        )

        return Response(
            {"data": serializer.data, "message": "Nomina actualizada exitosamente"}
        )

    @viewException
    def process_payroll(self, request: Request):
        """
        This endpoint is used to process de payroll payment
        """
        condition = dict_key_to_lower(request.data.get("condition"))
        if not condition:
            raise PayloadValidationError("condition es requerido")

        payroll = Payroll.objects.filter(simple_query_filter(condition)).first()
        if not payroll:
            raise PayloadValidationError(
                "No se encontro ningun resultado con la condition"
            )

        payroll.process_payroll(request)
        Payroll.update(request, payroll, status=Payroll.DONE)

        return Response({"message": "Nómina procesada exitosamente"})

    @viewException
    def process_partial_payroll(self, request: Request):
        """
        TThis endpoint is used to process partial payroll,
        meaning you can choose which employes you wnat to pay\n
        `METHOD` POST
        """
        condition: dict = request.data.get("condition", {})
        if not condition:
            raise PayloadValidationError("Condition is required")

        users: list[int] = condition.pop("USERS", [])
        if not users:
            raise PayloadValidationError("la lista de USERS es requerido.")

        payroll_id: int = condition.pop("PAYROLL_ID", None)
        if not payroll_id:
            raise PayloadValidationError("Payroll_id es requerido")

        payroll = Payroll.objects.get(payroll_id=payroll_id)
        if not payroll:
            raise APIException("Nómina no encontrada")

        entries = PayrollEntry.objects.filter(
            Q(user__username__in=users) & Q(payroll=payroll)
        )
        if not all(entry.status is False for entry in entries):
            raise PayloadValidationError(
                "La nómina de uno o más empleados de los seleccionados ya ha sido procesada."
            )

        users = entries.values_list("user__user_id", flat=True)

        payroll.process_payroll(request, users)

        if not PayrollEntry.objects.filter(
            Q(state=PayrollEntry.ACTIVE) & Q(status=False)
        ).exists():
            Payroll.update(request, payroll, status=Payroll.DONE)

        return Response({"message": "Entradas de nomina procesadas exitosamente"})

    @viewException
    def get_payrolls(self, request: Request):
        """
        Get a list of payrolls
        """
        condition = request.data.get("condition", None)
        if not condition:
            raise PayloadValidationError("Condition is required")

        if not isinstance(condition, dict):
            raise PayloadValidationError("Condition must be a dictionary")

        if not condition.get("PAYROLL_ID"):
            raise PayloadValidationError("Payroll ID is required in the condition")

        payroll = Payroll.objects.filter(simple_query_filter(condition)).first()
        if not payroll:
            raise NotFound("Payroll with the provided condition not found")

        serializer = PayrollSerializer(
            payroll, data=model_to_dict(payroll), context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        return Response({"data": serializer.data})

    @viewException
    def get_payroll_history(self, request: Request):
        """
        Get a history of payrolls with their payment details\n
        `METHOD`: POST
        """
        conditions = request.data.get("condition")

        if not conditions:
            raise APIException("The condition are required")
        if not isinstance(conditions, list):
            raise APIException("Invalid condition")

        condition, exclude = advanced_query_filter(conditions)

        payrolls = Payroll.objects.filter(condition)

        for ex in exclude:
            payrolls = payrolls.exclude(**ex)

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(payrolls.distinct(), request)

        serializer = PayrollHistorySerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)

    @viewException
    def get_payroll(self, request: Request):
        """
        Get a payroll with all entries\n
        `METHOD` POST
        """
        condition = request.data.get("condition", None)

        if not condition:
            raise PayloadValidationError("condition es requerido.")

        payroll = Payroll.objects.filter(simple_query_filter(condition)).first()
        if not payroll:
            raise APIException("Any payroll was found with the given condition")

        data = model_to_dict(payroll)

        serializer = PayrollSerializer(payroll, data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        return Response({"data": serializer.data})

    @viewException
    def get_payroll_info(self, request: Request):
        """
        This endpoint return info about the current payroll\n
        `METHOD` GET
        """

        payroll = Payroll.objects.latest("created_at")
        if not payroll:
            raise APIException(
                "No se encontro ninguna nómina acitiva y pendiente de pago."
            )

        serializer = PayrollInfoSerializer(payroll, data=model_to_dict(payroll))
        serializer.is_valid(raise_exception=False)

        return Response({"data": serializer.data})

    @viewException
    def get_payroll_entries(self, request: Request):
        """
        Get a list of payroll entries\n
        `METHOD` POST
        """
        conditions = request.data.get("condition")

        if not conditions:
            raise APIException("The condition are required")
        if not isinstance(conditions, list):
            raise APIException("Invalid condition")

        condition, exclude = advanced_query_filter(conditions)

        entries = PayrollEntry.objects.filter(condition)

        for ex in exclude:
            entries = entries.exclude(**ex)

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(entries.distinct(), request)

        seriazer = PayrollEntrySerializer(page, many=True, context={"request": request})

        return paginator.get_paginated_response(seriazer.data)

    @viewException
    def create_payroll_entry(self, request: Request):
        """
        Create a payroll entry
        `METHOD`: POST
        """
        data = dict_key_to_lower(request.data)
        for field in PayrollEntry.REQUIRED_FIELDS:
            if not data.get(field):
                raise APIException(
                    f"{field.upper()} is required",
                    PAYLOAD_VALIDATION_ERROR,
                )

        for field in data.keys():
            if field not in PayrollEntry.ALLOWED_FIELDS:
                raise APIException(
                    f"{field} is not allowed",
                    PAYLOAD_VALIDATION_ERROR,
                )

        payroll = Payroll.objects.get(payroll_id=data.get("payroll_id"))
        employees = User.objects.filter(username__in=data.get("employees"))

        entries = PayrollEntry.create_entries(payroll, employees, request.user)

        ActivityLog.register_activity(
            instance=entries,
            user=request.user,
            action=1,
            message=f"{request.user.username} agregó a {entries.count()} a la {str(payroll)}",
        )
        return Response({"message": "Entradas de nomina registradas exitosamente"})

    @viewException
    def update_payroll_entry(self, request: Request):
        """
        Update the state for a payroll entry\n
        `METHOD` POST
        """
        data = dict_key_to_lower(request.data)
        state = data.get("state", None)
        entry_id = data.get("payroll_entry_id", None)

        if not state:
            raise PayloadValidationError("STATE is required")
        if not entry_id:
            raise PayloadValidationError("PAYROLL_ENTRY_ID is required")

        entry = PayrollEntry.objects.get(payroll_entry_id=entry_id)
        if not entry:
            raise PayloadValidationError(
                f"Any payroll entry with id '{entry_id}' was found"
            )
        if entry.status:
            raise APIException(
                "No puede Inhabolidar esta entrada de nómina por que ya\
                    se le ha realizado el pago correspondiente al periodo actual"
            )

        state_str = "Inhabilito" if state == "I" else "Habilito"

        PayrollEntry.update(request, entry, state=state)

        ActivityLog.register_activity(
            instance=entry,
            user=request.user,
            action=2,
            message=f"@{request.user.username} {state_str} a @{entry.user.username} de la nómináde este periodo",
        )

        return Response({"message": "Entrada de nómina actualizada con exito"})

    @viewException
    def create_adjustment(self, request: Request):
        """
        Add justment to payroll entry\n
        `METHOD` POST
        """
        data = dict_key_to_lower(request.data)

        username = data.pop("username", None)
        if not username:
            raise PayloadValidationError("USERNAME es requerido")

        user = User.objects.get(username=username)
        if not user:
            raise PayloadValidationError(f"Usuario '{username}' no encontrado")

        payroll_id = data.pop("payroll_id", None)
        if not payroll_id:
            raise PayloadValidationError("PAYROLL_ID es requerido")

        payroll = Payroll.objects.get(payroll_id=payroll_id)
        if not payroll:
            raise PayloadValidationError(f"Nomina con id '{payroll_id}' No encontrada")

        payroll_entry = PayrollEntry.objects.filter(
            Q(user=user) & Q(payroll_id=payroll_id)
        ).first()

        if not payroll_entry:
            raise NotFound(
                f"La entrada de nomina para el usuario '@{username}' no fue encontrada"
            )

        concept = Concept.objects.filter(
            name=dict(Adjustment.ADJUSTMENT_TYPE).get(data["type"])
        ).first()

        data["concept"] = concept
        data["payroll_entry"] = payroll_entry

        adjustment = Adjustment(**data)
        adjustment = adjustment.create_adjustment(request, **data)

        adjustment_type = "DESCUENTO" if adjustment.type == "D" else "BONO"

        ActivityLog.register_activity(
            instance=adjustment,
            user=request.user,
            action=1,
            message=f"@{request.user.username} agrego un {adjustment_type} al usuario @{username}",
        )

        return Response({"message": "Registro completado con exito."})

    @viewException
    def update_adjustment(self, request: Request):
        """
        Update adjustments\n
        `METHOD` PUT
        """
        data = dict_key_to_lower(request.data)

        _type = data.get("type", None)
        adjustemt_type = "Bono" if _type == "B" else "Descuento"

        adjustment_id = data.get("adjustment_id", None)
        if not adjustment_id:
            raise PayloadValidationError("")

        payroll = data.pop("payroll", None)
        if not payroll:
            raise PayloadValidationError("Payroll is required")

        payroll = Payroll.objects.get(payroll_id=payroll)
        if not payroll:
            raise APIException(f"Payroll with id '{payroll}' was found")

        username = data.get("username")
        payroll_entry = PayrollEntry.objects.filter(
            Q(user__username=username) & Q(payroll=payroll)
        ).first()

        adjustemt = Adjustment.objects.filter(
            Q(adjustment_id=adjustment_id) & Q(payroll_entry=payroll_entry)
        ).first()

        if not adjustemt:
            raise NotFound(
                f"No se encontro ningun {adjustemt_type} con id '{adjustment_id}'"
            )

        Adjustment.update(request, adjustemt, **data)

        ActivityLog.register_activity(
            instance=adjustemt,
            user=request.user,
            action=2,
            message=f"@{request.user.username} actualizo un {adjustemt_type} del usuario @{username}",
        )

        return Response({"message": f"{adjustemt_type} acualizado exitosamente."})

    @viewException
    def get_adjustments(self, request: Request):
        """ "
        Get a list of ajustmets filtered by a condition\n
        `METHOD` POST
        """
        conditions = request.data.get("condition", None)

        if not conditions:
            raise PayloadValidationError("The condition is required")
        if not isinstance(conditions, list):
            raise PayloadValidationError("Invalid condition format")

        condition, exclude_condition = advanced_query_filter(conditions)

        adjustments = Adjustment.objects.filter(condition)

        for exclude in exclude_condition:
            adjustments = adjustments.exclude(**exclude)

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(adjustments, request)

        serializer = AdjustmentSerializer(page, many=True, context={"request": request})

        return paginator.get_paginated_response(serializer.data)

    @viewException
    def get_deduction_list(self, request: Request):
        """
        This endpoind acept a condition with all fields in the model `Deductions`\n
        and return the deductions that match with the given condition
        `METHOD` POST
        """
        condition = dict_key_to_lower(request.data.get("condition", None))

        if not condition:
            raise PayloadValidationError("condition is required.")
        if not isinstance(condition, dict):
            raise PayloadValidationError("The condition give an invalide format.")

        deductions = Deductions.objects.filter(simple_query_filter(condition))

        serializer = DeductionSerializer(
            deductions, many=True, context={"request": request}
        )

        return Response({"data": serializer.data})
