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
from payroll.reports import PayrollRepostService
from payroll._reports.payroll_report import (
    generate_payroll_report,
    payroll_entries_payment,
)
from payroll.serializers import (
    AdjustmentSerializer,
    DeductionSerializer,
    PayrollEntryReportSerializer,
    PayrollEntrySerializer,
    PayrollHistorySerializer,
    PayrollInfoSerializer,
    PayrollPaymentReportSerializer,
    PayrollSerializer,
)
from payroll.services import PayrollService
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
                message=f"@{request.user.username} registro la {str(payroll)}",
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
            message=f"@{request.user.username} actualizo la {str(payroll)}",
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
                "No se encontró ningún resultado con la condition"
            )

        service = PayrollService(payroll, request)

        service.process_payroll(users_id=condition.get("users", []))

        return Response({"message": "Nómina procesada exitosamente"})

    @viewException
    def process_partial_payroll(self, request: Request):
        """
        TThis endpoint is used to process partial payroll,
        meaning you can choose which employs you want to pay\n
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

        service = PayrollService(payroll, request)

        service.process_payroll(users)

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
                "No se encontró ninguna nómina activa y pendiente de pago."
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

        serializer = PayrollEntrySerializer(
            page, many=True, context={"request": request}
        )

        return paginator.get_paginated_response(serializer.data)

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
            message=f"@{request.user.username} agregó a {
                entries.count()} a la {str(payroll)}",
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
                "No puede Inhabilitar esta entrada de nómina por que ya\
                    se le ha realizado el pago correspondiente al periodo actual"
            )

        state_str = "Inhabilito" if state == "I" else "Habilito"

        PayrollEntry.update(request, entry, state=state)

        ActivityLog.register_activity(
            instance=entry,
            user=request.user,
            action=2,
            message=f"@{request.user.username} {state_str} a @{
                entry.user.username} de la nómina de este periodo",
        )

        return Response({"message": "Entrada de nómina actualizada con éxito"})

    @viewException
    def create_adjustment(self, request: Request):
        """
        Add adjustment to payroll entry\n
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
                f"La entrada de nomina para el usuario '@{
                    username}' no fue encontrada"
            )

        data["payroll_entry"] = payroll_entry
        data["concept"] = Concept.objects.get(concept_id=data.get("concept"))

        adjustment = Adjustment(**data)
        adjustment: Adjustment = adjustment.create_adjustment(request, **data)

        ActivityLog.register_activity(
            instance=adjustment,
            user=request.user,
            action=1,
            message=f"@{request.user.username} agrego un {
                adjustment.concept.name} al usuario @{username}",
        )

        return Response({"message": "Registro completado con éxito."})

    @viewException
    def update_adjustment(self, request: Request):
        """
        Update adjustments\n
        `METHOD` PUT
        """
        data = dict_key_to_lower(request.data)

        concept = data.get("concept", None)
        concept = Concept.objects.get(concept_id=concept)

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

        adjustment = Adjustment.objects.filter(
            Q(adjustment_id=adjustment_id) & Q(payroll_entry=payroll_entry)
        ).first()

        if not adjustment:
            raise NotFound(
                f"No se encontró ningún {
                    concept.name} con id f'{adjustment_id}'"
            )

        Adjustment.update(request, adjustment, **data)

        ActivityLog.register_activity(
            instance=adjustment,
            user=request.user,
            action=2,
            message=f"@{request.user.username} actualizo un {
                concept.name} del usuario @{username}",
        )

        return Response({"message": f"{concept.name} acuatizado exitosamente."})

    @viewException
    def get_adjustments(self, request: Request):
        """ "
        Get a list of adjustments filtered by a condition\n
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
        This endpoint accept a condition with all fields in the model `Deductions`\n
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

    @viewException
    def generate_dynamic_report(
        self, request: Request, rp_name: str, entry_id: int = None
    ):
        base64_pdf = ""

        rp_service = PayrollRepostService(
            f"{request.user.name} {request.user.last_name}", True
        )

        conditions = request.data

        if not conditions:
            raise APIException("The condition are required")
        if not isinstance(conditions, list):
            raise APIException("Invalid condition")

        condition, exclude = advanced_query_filter(conditions)

        entries = PayrollEntry.objects.filter(condition)

        for ex in exclude:
            entries = entries.exclude(**ex)

        payroll = entries.first().payroll

        context = {"request": request}

        match rp_name:
            case "payment_detail":
                entry = entries.first()
                if entry_id:
                    rp_title = f"Detalle de pago de {repr(entry.user)} \
                        correspondiente a la {str(payroll)}"
                else:
                    rp_title = f"Detalles de pago correspondientes a la {str(payroll)}"

                serializer = PayrollPaymentReportSerializer(
                    entries, many=True, context=context
                )
                base64_pdf = rp_service.payment_details(serializer.data, rp_title)
            case "current_payroll":
                rp_title = str(payroll)
                serializer = PayrollEntryReportSerializer(
                    entries, many=True, context=context
                )

                base64_pdf = rp_service.payroll(serializer.data, rp_title)
            case _:
                raise APIException("Invalid report name.")

        return Response({"data": base64_pdf})

    @viewException
    def generate_report(self, request: Request):
        conditions = request.data.get("condition")

        if not conditions:
            raise APIException("The condition are required")
        if not isinstance(conditions, list):
            raise APIException("Invalid condition")

        condition, exclude = advanced_query_filter(conditions)

        entries = PayrollEntry.objects.filter(condition)

        for ex in exclude:
            entries = entries.exclude(**ex)

        serializer = PayrollEntryReportSerializer(
            entries, many=True, context={"request": request}
        )

        base64_pdf = generate_payroll_report(
            data=serializer.data,
            title=str(entries.first().payroll),
            user=f"{request.user.name} {request.user.last_name}",
            is_landscape=True,
        )

        return Response({"data": base64_pdf})

    @viewException
    def payment_history_report(self, request: Request, payroll_entry_id: int):
        payroll_entries = None
        title = ""
        if request.method == "POST":
            conditions = request.data.get("condition")

            if not conditions:
                raise APIException("The condition are required")
            if not isinstance(conditions, list):
                raise APIException("Invalid condition")

            condition, exclude = advanced_query_filter(conditions)

            payroll_entries = PayrollEntry.objects.filter(condition)

            title = str(payroll_entries.first().payroll)

            for ex in exclude:
                payrolls = payrolls.exclude(**ex)
        else:
            payroll_entries = PayrollEntry.objects.filter(
                payroll_entry_id=payroll_entry_id
            )

            entry = payroll_entries.first()

            title = f"Detalle de pago de {repr(entry.user)} correspondiente a la {str(entry.payroll)}"

        serializer = PayrollPaymentReportSerializer(
            payroll_entries,
            many=True,
            context={"request": request, "capitalize": False},
        )
        base64_pdf = payroll_entries_payment(
            data=serializer.data,
            title=title,
            is_landscape=True,
            user=f"{request.user.name} {request.user.last_name}",
        )

        return Response({"data": base64_pdf})
