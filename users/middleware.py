from datetime import datetime
from django.utils.deprecation import MiddlewareMixin
from django.utils.timezone import now
from django.http import JsonResponse


class PaymentValidationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        payment_date = datetime(2024, 11, 20)
        if payment_date < now().date():
            return JsonResponse(
                {"error": "Su cuenta ha sido suspendida por falta de pago."},
                status=403,
            )
        return None
