import traceback
from functools import wraps
from django.forms import ValidationError
from django.core.exceptions import FieldError, ObjectDoesNotExist
from rest_framework.exceptions import APIException
from rest_framework.response import Response


def get_traceback():
    print("*" * 75)
    print(f"traceback: {traceback.format_exc()}")
    print("*" * 75)
    return traceback.format_exc()


class CustomBaseException(Exception):
    """
    CustomBaseException is the base class for custom exceptions in the application.
    """

    def __init__(self, message, status_code=None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        return f"{self.__class__.__name__}: {self.message}"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.message!r})"


class UserException(CustomBaseException):
    """
    UserException is a class that inherits from CustomBaseException
    and is used to raise exceptions related to the User model.
    """

    def __init__(self, message, status_code=None):
        super().__init__(message, status_code)
        self.message = message
        self.status_code = status_code


class UserDoesNotExist(UserException):
    """
    UserDoesNotExist is a class that inherits from UserException
    and is used to raise exceptions when a user does not exist.
    """

    def __init__(self, message="User does not exist", status_code=404):
        super().__init__(message, status_code)
        self.message = message
        self.status_code = status_code


class CustomValidationError(ValidationError):
    """
    CustomValidationError is a class that inherits from ValidationError
    and is used to raise custom validation errors.
    """

    def __init__(self, message, code=None, e_code="ValidationError"):
        super().__init__(message, code)
        self.message = message
        self.code = code or e_code


class PayloadValidationError(APIException):
    """
    PayloadValidationError is a class that inherits from APIException
    and is used to raise exceptions related to payload validation.
    """

    def __init__(self, message, code=None, status_code=400):
        super().__init__(message, code)
        self.message = message
        self.code = code or "PayloadValidationError"
        self.status_code = status_code


def viewException(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (
            PayloadValidationError,
            APIException,
            TypeError,
            AttributeError,
            ValueError,
            ValidationError,
            FieldError,
            ObjectDoesNotExist,
        ) as e:
            error_code = getattr(e, "code", e.__class__.__name__)
            status_code = getattr(
                e,
                "status_code",
                (
                    400
                    if isinstance(
                        e,
                        (
                            TypeError,
                            AttributeError,
                            ValueError,
                            ValidationError,
                            FieldError,
                        ),
                    )
                    else 500
                ),
            )
            get_traceback()
            return Response({"error": str(e), "code": error_code}, status=status_code)
        # pylint: disable=broad-except
        except Exception as e:
            get_traceback()
            return Response({"error": str(e), "code": e.__class__.__name__}, status=500)

    return wrapper
