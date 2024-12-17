from decimal import Decimal
from typing import List, Optional
from django.db import transaction
from django.db.models import Q
from rest_framework.request import Request

from payroll.models import (
    Adjustment,
    Concept,
    DeductionXuser,
    Payroll,
    PayrollEntry,
    PayrollPaymentDetail,
    PayrollSettings,
)
from time_management.models import Leaves, Overtime


class PayrollService:
    """
    Servicio para procesar una nómina.
    """

    SALARY_CONCEPT_NAME = "SALARIO"
    ZERO = Decimal("0.0")

    def __init__(self, payroll: Payroll, request: Request):
        self.payroll = payroll
        self.user = request.user

    @transaction.atomic
    def process_payroll(self, users_id: Optional[List[int]] = None) -> Payroll:
        """
        Procesa una nómina para los usuarios especificados o para todos los usuarios asociados a la nómina.
        """

        if users_id and not all(isinstance(user_id, int) for user_id in users_id):
            raise ValueError("users_id debe ser una lista de enteros.")

        settings = self.payroll.get_config()
        apply_deduction = settings.periods == self.payroll.period
        payroll_entries = self._get_payroll_entries(users_id)

        # Pre-cargar conceptos necesarios
        salary_concept = Concept.objects.filter(name=self.SALARY_CONCEPT_NAME).first()
        if not salary_concept:
            raise ValueError(
                f"El concepto {self.SALARY_CONCEPT_NAME} no está configurado en la base de datos."
            )

        # Procesar cada entrada de nómina
        processed_entries = []
        for entry in payroll_entries:
            totals = self._process_entry(entry, apply_deduction)
            self._finalize_payroll_entry(entry, totals, settings, apply_deduction)
            entry.status = True
            processed_entries.append(entry)

        PayrollEntry.objects.bulk_update(processed_entries, ["status"])

        if not PayrollEntry.objects.filter(
            Q(state=PayrollEntry.ACTIVE) & Q(status=False)
        ).exists():
            self.payroll.status = Payroll.DONE
            self.payroll.save(update_fields=["status"])

        return self.payroll

    def _get_payroll_entries(self, users_id: Optional[List[int]]) -> list[PayrollEntry]:
        """
        Obtiene las entradas de nómina según los usuarios especificados.
        """
        payroll_entries = PayrollEntry.objects.filter(
            payroll_id=self.payroll.payroll_id
        )
        if users_id:
            payroll_entries = payroll_entries.filter(user__user_id__in=users_id)

        return payroll_entries.select_related("user")

    def _process_entry(
        self, entry: PayrollEntry, apply_deduction: bool
    ) -> dict[str, Decimal]:
        """
        Procesa todos los elementos de una entrada de nómina y acumula los totales.
        """
        totals = {
            "overtime": self.ZERO,
            "paid_leaves": self.ZERO,
            "discount_leaves": self.ZERO,
            "deductions": self.ZERO,
            "adjustments": self.ZERO,
        }

        totals["deductions"] += self._process_deductions(entry, apply_deduction)
        totals["adjustments"] += self._process_adjustments(entry)
        totals["overtime"] += self._process_overtimes(entry)
        totals.update(self._process_leaves(entry))

        return totals

    def _process_deductions(
        self, entry: PayrollEntry, apply_deduction: bool
    ) -> Decimal:
        """
        Procesa y acumula las deducciones para una entrada de nómina.
        """
        if not apply_deduction:
            return self.ZERO

        deductions: list[DeductionXuser] = DeductionXuser.get_user_deductions(
            entry.user
        )
        total_deductions = self.ZERO

        for deduction in deductions:
            amount = DeductionXuser.get_deduction_amount(
                entry.user, deduction.deduction.name
            )
            comment = f"Descuento mensual por concepto de {deduction.deduction.name}"
            self._create_payroll_detail(
                entry, deduction.deduction.concept, amount, "-", comment
            )
            total_deductions += amount

        return total_deductions

    def _process_adjustments(self, entry: PayrollEntry) -> Decimal:
        """
        Procesa y acumula los ajustes para una entrada de nómina.
        """
        adjustments = Adjustment.get_by_entry(entry)
        total_adjustments = self.ZERO

        for adjustment in adjustments:
            amount = Adjustment.get_amount(entry, adjustment.concept)
            self._create_payroll_detail(
                entry,
                adjustment.concept,
                amount,
                adjustment.concept.operator,
                adjustment.description,
            )
            total_adjustments += amount

        adjustments.update(state=Adjustment.COMPLETED)
        return total_adjustments

    def _process_overtimes(self, entry):
        """
        Procesa y acumula las horas extras para una entrada de nómina.
        """
        if not self.payroll.includes_overtime:
            return self.ZERO

        overtimes = entry.get_employee_overtime()
        total_hours = Decimal("0.0")
        total_overtime = self.ZERO

        for overtime in overtimes:
            total_hours += overtime.hours
            total_overtime += overtime.get_amount()
            overtime.paid = True

        if total_overtime > self.ZERO:
            concept = overtimes.first().concept
            comment = f"{total_hours} horas por un total de:"
            self._create_payroll_detail(entry, concept, total_overtime, "+", comment)

        Overtime.objects.bulk_update(overtimes, ["paid"])
        return total_overtime

    def _process_leaves(self, entry: PayrollEntry) -> list[str, Decimal]:
        """
        Procesa y acumula licencias pagadas y descontadas.
        """
        totals = {"paid_leaves": self.ZERO, "discount_leaves": self.ZERO}

        for leave in entry.get_leaves(True):
            self._create_leave_detail(entry, leave, "+", "Pago")
            totals["paid_leaves"] += leave.amount

        for leave in entry.get_leaves(False):
            self._create_leave_detail(entry, leave, "-", "Descuento")
            totals["discount_leaves"] += leave.amount

        return totals

    def _create_leave_detail(
        self, entry: PayrollEntry, leave: Leaves, operator: str, action: str
    ) -> None:
        """
        Crea un detalle para una licencia.
        """
        leave.state = Leaves.DONE
        comment = f"{action} por concepto de {leave.concept.name}"
        self._create_payroll_detail(
            entry, leave.concept, leave.amount, operator, comment
        )

        leave.save(update_fields=["state"])

    def _finalize_payroll_entry(
        self,
        entry: PayrollEntry,
        totals: list[str, Decimal],
        settings: PayrollSettings,
        apply_deduction: bool,
    ) -> None:
        """
        Calcula y finaliza el salario neto para una entrada de nómina.
        """
        afp = DeductionXuser.get_afp(entry.user) if apply_deduction else self.ZERO
        sfs = DeductionXuser.get_sfs(entry.user) if apply_deduction else self.ZERO
        isr = DeductionXuser.get_isr(entry.user) if apply_deduction else self.ZERO

        salary = entry.user.salary / settings.periods
        net_salary = (
            salary
            + totals["adjustments"]
            + totals["overtime"]
            + totals["paid_leaves"]
            - totals["discount_leaves"]
            - afp
            - sfs
            - isr
        )

        self._create_payroll_detail(
            entry,
            Concept.objects.get(name=self.SALARY_CONCEPT_NAME),
            net_salary,
            "+",
            "Salario neto",
        )

    def _create_payroll_detail(
        self,
        entry: PayrollEntry,
        concept: Concept,
        amount: Decimal,
        operator: str,
        comment: str,
    ) -> None:
        """
        Crea un detalle de pago de nómina.
        """
        PayrollPaymentDetail.objects.create(
            payroll=entry.payroll,
            payroll_entry=entry,
            concept=concept,
            period=self.payroll.period,
            concept_amount=amount,
            state=PayrollPaymentDetail.ACTIVE,
            created_by=self.user,
            gross_salary=entry.user.salary,
            operator=operator,
            comment=comment,
        )
