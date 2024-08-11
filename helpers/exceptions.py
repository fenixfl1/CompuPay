import traceback
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


def get_traceback():
    print("*" * 75)
    print(f"traceback: {traceback.format_exc()}")
    print("*" * 75)
    return traceback.format_exc()


def viewException(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (APIException, CustomBaseException) as e:
            get_traceback()
            return Response({"error": str(e)}, status=e.status_code or 500)

    return wrapper
