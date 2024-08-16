import traceback
from django.forms import ValidationError
from rest_framework.exceptions import APIException
from rest_framework.response import Response


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


def get_traceback():
    print("*" * 75)
    print(f"traceback: {traceback.format_exc()}")
    print("*" * 75)
    return traceback.format_exc()


def viewException(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except APIException as e:
            return Response(
                {"error": str(e), "code": e.get_codes()}, status=e.status_code or 500
            )
        except TypeError as e:
            get_traceback()
            return Response({"error": str(e), "code": "TypeError"}, status=400)
        except AttributeError as e:
            get_traceback()
            return Response({"error": str(e), "code": "AttributeError"}, status=400)
        except ValueError as e:
            return Response({"error": str(e), "code": "ValueError"}, status=400)
        except ValidationError as e:
            return Response(
                {"error": str(e), "code": e.code or "ValidationError"}, status=400
            )
        # pylint: disable=broad-except
        except Exception as e:
            # pylint: disable=no-member
            return Response({"error": str(e), "code": e.code}, status=500)

    return wrapper
