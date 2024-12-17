# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from payroll.services import PayrollService
from payroll.models import (
    Adjustment,
    Concept,
    Deductions,
    DeductionXuser,
    Payroll,
    PayrollEntry,
    PayrollPaymentDetail,
)
from time_management.models import Leaves, Overtime

User = get_user_model()


@pytest.fixture
def setup_test_data(db):
    """
    Configura datos iniciales de prueba
    """
    user = User.objects.get(user_id=2)

    payroll = Payroll.objects.create(
        name="Test Payroll",
        period=1,
        includes_overtime=True,
        includes_leaves=True,
    )

    payroll_entry = PayrollEntry.objects.create(
        payroll=payroll,
        user=user,
        status=False,
    )

    concept_salary = Concept.objects.create(
        name="SALARIO",
        operator="+",
    )

    overtime_concept = Concept.objects.create(
        name="Horas Extras",
        operator="+",
    )

    leave_concept = Concept.objects.create(
        name="Licencia",
        operator="-",
    )

    adjustment_concept = Concept.objects.create(
        name="Ajuste Bono",
        operator="+",
    )

    deduction = Deductions.objects.create(
        name="SFS",
        concept=concept_salary,
    )

    DeductionXuser.objects.create(
        user=user,
        deduction=deduction,
        amount=Decimal("100.00"),
    )

    Adjustment.objects.create(
        entry=payroll_entry,
        type="B",
        concept=adjustment_concept,
        amount=Decimal("50.00"),
        state=Adjustment.PENDING,
    )

    Overtime.objects.create(
        user=user,
        concept=overtime_concept,
        hours=5,
        rate=Decimal("10.00"),
        paid=False,
    )

    Leaves.objects.create(
        user=user,
        concept=leave_concept,
        amount=Decimal("50.00"),
        state=Leaves.PENDING,
    )

    return {
        "user": user,
        "payroll": payroll,
        "payroll_entry": payroll_entry,
        "concept_salary": concept_salary,
        "overtime_concept": overtime_concept,
        "leave_concept": leave_concept,
        "adjustment_concept": adjustment_concept,
    }


@pytest.fixture
def api_request_factory():
    """
    Configura una APIRequestFactory para las pruebas
    """
    return APIRequestFactory()


def test_process_payroll_success(setup_test_data, api_request_factory):
    data = setup_test_data
    request = api_request_factory.get("/api/payroll/")
    request.user = data["user"]

    service = PayrollService(payroll=data["payroll"], request=request)

    # Procesar la nómina
    processed_payroll = service.process_payroll(users_id=[data["user"].id])

    assert processed_payroll == data["payroll"]

    # Verificar que la entrada de nómina se procesó
    assert PayrollEntry.objects.filter(
        payroll=data["payroll"], user=data["user"], status=True
    ).exists()

    # Verificar detalles de nómina
    payment_details = PayrollPaymentDetail.objects.filter(
        payroll=data["payroll"], payroll_entry=data["payroll_entry"]
    )

    # Verificar salario neto
    net_salary_detail = payment_details.filter(concept=data["concept_salary"]).first()
    assert net_salary_detail is not None
    assert net_salary_detail.concept_amount > Decimal("0.0")

    # Verificar deducciones
    assert payment_details.filter(concept=data["concept_salary"], operator="-").exists()

    # Verificar ajustes
    assert payment_details.filter(
        concept=data["adjustment_concept"], operator="+"
    ).exists()

    # Verificar horas extras
    assert payment_details.filter(
        concept=data["overtime_concept"], operator="+"
    ).exists()

    # Verificar licencias
    assert payment_details.filter(concept=data["leave_concept"], operator="-").exists()


def test_process_payroll_no_users(setup_test_data, api_request_factory):
    data = setup_test_data
    request = api_request_factory.get("/api/payroll/")
    request.user = data["user"]

    service = PayrollService(payroll=data["payroll"], request=request)

    # Procesar sin usuarios
    _processed_payroll = service.process_payroll()

    # Verificar que se procesó la nómina para todos
    payroll_entries = PayrollEntry.objects.filter(payroll=data["payroll"], status=True)
    assert payroll_entries.count() == 1


def test_process_payroll_invalid_users_id(setup_test_data, api_request_factory):
    data = setup_test_data
    request = api_request_factory.get("/api/payroll/")
    request.user = data["user"]

    service = PayrollService(payroll=data["payroll"], request=request)

    # Intentar procesar con IDs inválidos
    with pytest.raises(ValueError):
        service.process_payroll(users_id=["invalid_id"])


def test_process_payroll_missing_salary_concept(setup_test_data, api_request_factory):
    data = setup_test_data

    # Eliminar concepto de salario
    data["concept_salary"].delete()

    request = api_request_factory.get("/api/payroll/")
    request.user = data["user"]

    service = PayrollService(payroll=data["payroll"], request=request)

    # Intentar procesar la nómina
    with pytest.raises(ValueError):
        service.process_payroll(users_id=[data["user"].id])
