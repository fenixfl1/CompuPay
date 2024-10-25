import datetime
from django.contrib.auth import authenticate, get_user_model
from django.forms.models import model_to_dict
from django.db.models import Q, Max
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated

from helpers.exceptions import (
    PayloadValidationError,
    UserDoesNotExist,
    UserException,
    viewException,
)
from helpers.serializers import DynamicSerializer, PaginationSerializer
from helpers.utils import (
    advanced_query_filter,
    dict_key_to_lower,
    list_values_to_lower,
    simple_query_filter,
)
from payroll.models import DeductionXuser
from users.models import (
    STATE_CHOICES,
    ActivityLog,
    Department,
    MenuOptions,
    Parameters,
    Roles,
    RolesUsers,
    User,
)
from users.serializers import (
    AuthenticateUserSerializer,
    MenuOptionsSerializer,
    RolesSerializer,
    UserSerializer,
)


class AuthenticationViewSet(ViewSet):
    """
    User authentication viewset. This viewset provides the following actions:
    - login: Authenticate a user and return a token.
    - logout: Invalidate a token.
    - refresh: Refresh a token.
    """

    permission_classes = [AllowAny]

    @viewException
    def login(self, request):
        """
        Authenticate a user and return a token.\n
        `METHOD`: POST
        """

        username = request.data.get("username", None)
        password = request.data.get("password", None)
        remember = request.data.get("remember", False)

        if not username or not password:
            raise UserException("Username and password are required")

        user = authenticate(username=username, password=password)

        if user is not None:
            if not user.is_staff and user.state != User.ACTIVE:
                raise APIException("This user cannot access the system")
        else:
            raise UserException("Invalid username or password")

        token, _ = Token.objects.get_or_create(user=user)

        expires = (
            datetime.datetime.now() + datetime.timedelta(days=30)
            if remember
            else datetime.datetime.now() + datetime.timedelta(days=1)
        )

        serializer = AuthenticateUserSerializer(
            instance=user,
            token=token.key,
            expires=expires,
            data=model_to_dict(user),
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        return Response(
            {
                "data": serializer.data,
                "message": f"Welcome @{user.username}",
            }
        )

    @viewException
    def logout(self, request):
        """
        Invalidate a token.\n
        `METHOD`: GET
        """

        request.user.auth_token.delete()

        return Response({"message": "Logout successful"})

    @viewException
    def refresh(self, request):
        """
        Refresh a token.\n
        `METHOD`: GET
        """

        token, _ = Token.objects.get_or_create(user=request.user)

        serializer = AuthenticateUserSerializer(
            token=token.key,
            expires=token.created + datetime.timedelta(days=1),
            instance=request.user,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        return Response(
            {
                "data": serializer.data,
                "message": "Token refreshed successfully",
            }
        )


class UserViewSet(ViewSet):
    """
    This viewset provides the following actions:\n
    >> - `list`: Return a list of users.
    >> - `create`: Create a new user.
    >> - `change` state: Change the state of a user.
    >> - `update`: Update the given user.
    >> - `assign_role`: Assign a role to a user.
    >> - `remove_role`: Remove a role from a user.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]
    pagination_class = PaginationSerializer
    serializer_class = UserSerializer

    @viewException
    def change_password(self, request):
        """
        Change the password of a user.\n
        `METHOD`: PUT
        """

        user = request.user

        data = dict_key_to_lower(request.data)

        if not data:
            raise APIException("The request body is empty")

        user_id = data.get("user_id", None)
        old_password = data.get("old_password", None)
        new_password = data.get("new_password", None)

        if user_id != user.user_id:
            raise UserException("Invalid user")

        if not old_password or not new_password:
            raise UserException("Old password and new password are required")

        if not user.check_password(old_password):
            raise UserException("Invalid old password")

        if old_password == new_password:
            raise UserException("Use a different password from the old one")

        user.set_password(new_password)
        user.save()

        return Response({"message": "Password changed successfully"})

    @viewException
    def check_username(self, request: Request):
        """
        This andpoint is used to check if an given username is available
        `METHOD`: POST
        """
        data = dict_key_to_lower(request.data)
        username = data.get("username", None)
        if not username:
            raise PayloadValidationError(
                "USERNAME is required", status_code=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(username=username).exists() is True:
            return Response(
                {"message": "El nombre de usuario ya esta en uso"},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {"message": "Nombre de usuario disponible."}, status=status.HTTP_200_OK
        )

    @viewException
    def check_identity_document(self, request: Request):
        """
        This andpoint is used to check if an given identity document is available
        `METHOD`: POST
        """
        data = dict_key_to_lower(request.data)
        document = data.get("identity_document", None)
        if not document:
            raise PayloadValidationError(
                "IDENTITY_DOCUMENT is required", status_code=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(identity_document=document).exists() is True:
            return Response(
                {"message": "El documento de identidad digitada ya existe."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {"message": "Documento de identidad disponible."}, status=status.HTTP_200_OK
        )

    @viewException
    def get_list_users(self, request):
        """
        Return a list of users.\n
        `METHOD`: POST
        """
        conditions: list[dict] = request.data.get("condition", None)
        fields = list_values_to_lower(request.data.get("fields", None))

        if not conditions:
            raise PayloadValidationError("The condition are required")
        if not isinstance(conditions, list):
            raise PayloadValidationError("Invalid condition")

        condition, exclude_condition = advanced_query_filter(conditions)

        users = User.objects.filter(condition)

        for exclude in exclude_condition:
            users = users.exclude(**exclude)

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(users.distinct(), request)

        serializer = []
        if fields:
            if not isinstance(fields, list):
                raise PayloadValidationError("Invalid format for field 'FIELDS'")
            serializer = DynamicSerializer(
                model=User, fields=fields, instance=page, many=True
            )
        else:
            serializer = UserSerializer(page, many=True, context={"request": request})

        return paginator.get_paginated_response(serializer.data)

    @viewException
    def get_user(self, request):
        """
        Return a user.\n
        `METHOD`: POST
        """
        condition: dict = request.data.get("condition", None)

        if not condition:
            raise APIException("The condition are required")

        user = User.objects.filter(simple_query_filter(condition)).first()

        if not user:
            raise UserDoesNotExist("User not found")

        serializer = UserSerializer(
            user, data=model_to_dict(user), context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        return Response({"data": serializer.data})

    def create_user(self, request):
        """
        Create a new user.\n
        `METHOD`: POST
        """
        data = dict_key_to_lower(request.data)

        if not data:
            raise APIException("The request body is empty")

        unique_fields = ["username", "email", "identity_document"]
        for field in unique_fields:
            if User.objects.filter(**{field: data.get(field)}).exists():
                raise APIException(
                    f"User with {field} '{data.get(field)}' already exists"
                )

        roles = data.get("roles", None)
        if not isinstance(roles, list):
            raise APIException("Invalid roles")
        if len(roles) > 0:
            roles = Roles.objects.filter(rol_id__in=roles)
            if not roles:
                raise APIException("Invalid roles")

        data["created_by"] = request.user

        if data.get("supervisor", None):
            data["supervisor"] = User.objects.get(username=data["supervisor"])

        if not data.get("password", None):
            data["password"] = Parameters.objects.get(name="DEFAULT_PASSWORD").name

        deductions = data.pop("deductions", [])

        data["department"] = Department.objects.get(department_id=data["department"])

        user: User = User.objects.create_user(**data)

        try:
            DeductionXuser.add_deductions_to_user(deductions, user)
        except Exception as e:
            RolesUsers.objects.filter(user_id=user.user_id).delete()
            user.delete()
            raise APIException(str(e)) from e

        ActivityLog.register_activity(
            instance=user,
            user=request.user,
            action=1,
            message=f"@{request.user.username} creo al usuario @{user.username}",
        )

        setializer = UserSerializer(
            user, data=model_to_dict(user), context={"request": request}
        )
        setializer.is_valid(raise_exception=True)

        return Response(
            {"data": setializer.data, "message": "User created successfully"}
        )

    @viewException
    def change_state(self, request):
        """
        Change the state of a user.\n
        `METHOD`: PUT
        """
        data = dict_key_to_lower(request.data)

        user_id = data.get("user_id", None)
        state = data.get("state", None)

        valid_states = [state for state, _ in User.STATE_CHOICES]

        if state not in valid_states:
            raise APIException(f"Invalid state '{state}'")

        user = User.objects.get(user_id=user_id)

        if not user:
            raise UserDoesNotExist(f"User with id: '{user_id}' was not found.")

        user.state = state
        user.save()

        action = "inhabilitó" if state == "I" else "activo"

        ActivityLog.register_activity(
            instance=user,
            user=request.user,
            action=2,
            message=f"@{request.user.username} {action} al usuario @{user.username}",
        )

        return Response({"message": "User state changed successfully."})

    def update_user(self, request: Request):
        """
        Update the given user.\n
        `METHOD`: PUT
        """
        data = dict_key_to_lower(request.data)

        user_id = data.get("user_id", None)
        if not user_id:
            raise APIException("user_id id is required.")

        user = User.objects.get(user_id=user_id)
        if not user:
            raise UserDoesNotExist(
                f"User with id: '{data.get('user_id')}' was not found."
            )

        for field in data:
            if field in User.NON_UPDATEABLE_FIELDS:
                raise APIException(f"Field '{field}' is not updatable.")

        supervisor = data.get("supervisor", None)
        if supervisor:
            data["supervisor"] = User.objects.get(username=supervisor)
            if not data["supervisor"]:
                raise APIException(f"Supervisor '{supervisor}' was not found.")

        roles = data.pop("roles", None)
        if roles:
            roles = Roles.objects.filter(rol_id__in=roles)
            if not roles:
                raise APIException("Invalid roles")

        deductions = data.pop("deductions")

        message = "User updated successfully."

        if roles:
            try:
                roles_users = RolesUsers.objects.filter(user_id=user)
                if roles_users:
                    roles_users.update(state=RolesUsers.INACTIVE)
                for role in roles:
                    usr_role = RolesUsers.objects.get(Q(rol_id=role) & Q(user_id=user))
                    if usr_role:
                        usr_role.state = RolesUsers.ACTIVE
                        usr_role.save()
                    else:
                        RolesUsers.create(
                            request, user_id=user, rol_id=role, state=RolesUsers.ACTIVE
                        )
            # pylint: disable=broad-except
            except Exception:
                message = "User updated successfully. But an error occurred while assigning roles."

        if deductions:
            try:
                DeductionXuser.add_deductions_to_user(deductions, user)
            # pylint: disable=broad-except
            except Exception:
                message = "User updated successfully. But an error occurred while assigning deductions"

        department = data.get("department", None)
        if department:
            data["department"] = Department.objects.get(department_id=department)

        user = User.update_user(request, **data)

        data = model_to_dict(user)

        serializer = UserSerializer(user, data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        if user != request.user:
            ActivityLog.register_activity(
                instance=user,
                user=request.user,
                action=1,
                message=f"@{request.user.username} creo al usuario @{user.username}",
            )

        return Response({"data": serializer.data, "message": message})

    @viewException
    def update_avatar(self, request: Request):
        data = dict_key_to_lower(request.data)

        username = data.get("username")
        if not username:
            raise PayloadValidationError("USERNAME is required")

        user = User.objects.get(username=username)
        if not user:
            raise UserDoesNotExist("User not found.")

        user.avatar = data.get("avatar", None)
        user.save()

        return Response({"message": "El avatar se actualizo con exito."})

    @viewException
    def change_user_rol(self, request):
        """
        Assign a role to a user.\n
        `METHOD`: PUT
        """
        data = dict_key_to_lower(request.data)

        user_id = data.get("user_id", None)
        old_rol = data.get("old_rol", None)
        new_role = data.get("new_rol", None)

        user = User.objects.get(user_id=user_id)
        if not user:
            raise UserDoesNotExist(f"User with id: '{user_id}' was not found.")

        rol = Roles.objects.get(rol_id=new_role)

        roles_users = RolesUsers.objects.filter(
            Q(user_id=user_id) & Q(rol_id=old_rol)
        ).first()
        if not roles_users:
            raise APIException(
                f"User with id: '{user_id}' does not have the role '{old_rol}'."
            )

        RolesUsers.update(
            request,
            roles_users,
            rol_id=Roles.objects.get(rol_id=old_rol),
            user_id=user,
            state="I",
        )
        new_rol = RolesUsers.create(request, user_id=user, rol_id=rol, state="A")

        ActivityLog.register_activity(
            instance=new_rol,
            user=request.user,
            action=1,
            message=f"""
            @{request.user.username} cambio el rol {roles_users.rol_id.name} a \
                {new_rol.rol_id.name} para el usuario @{new_rol.get_username()}""",
        )

        return Response({"message": "Role change successfully."})

    @viewException
    def asign_role(self, request):
        """
        Assign a role to a user.\n
        `METHOD`: PUT
        """
        data = dict_key_to_lower(request.data)

        user_id = data.get("user_id", None)
        rol_id = data.get("rol_id", None)

        user = User.objects.get(user_id=user_id)
        if not user:
            raise UserDoesNotExist(f"User with id: '{user_id}' was not found.")

        role = Roles.objects.get(rol_id=rol_id)
        if not role:
            raise APIException(f"Role with id: '{rol_id}' was not found.")

        roles_users = RolesUsers.create(
            request, user_id=user, rol_id=role, state=RolesUsers.ACTIVE
        )

        ActivityLog.register_activity(
            instance=roles_users,
            user=request.user,
            action=1,
            message=f"@{request.user.username} asigno un rol a {user.username}",
        )

        return Response({"message": "Role assigned successfully."})

    @viewException
    def remove_role(self, request):
        """
        Remove a role from a user.\n
        `METHOD`: PUT
        """
        data = dict_key_to_lower(request.data)

        user_id = data.get("user_id", None)
        rol_id = data.get("rol_id", None)

        user = User.objects.get(user_id=user_id)
        if not user:
            raise UserDoesNotExist(f"User with id: '{user_id}' was not found.")

        role = Roles.objects.get(rol_id=rol_id)
        if not role:
            raise APIException(f"Role with id: '{rol_id}' was not found.")

        roles_users = RolesUsers.objects.filter(
            Q(user_id=user_id) & Q(rol_id=rol_id)
        ).first()
        if not roles_users:
            raise APIException(
                f"User with id: '{user_id}' does not have the role '{rol_id}'."
            )

        new_roles_users = RolesUsers.update(
            request,
            roles_users,
            rol_id=role,
            user_id=user,
            state=RolesUsers.INACTIVE,
        )

        ActivityLog.register_activity(
            instance=new_roles_users,
            user=request.user,
            action=2,
            message=f"@{request.user.username} le removio su rol a {user.username}",
        )

        return Response({"message": "Role removed successfully."})

    @viewException
    def get_roles_list(self, request):
        """
        Return a list of roles assigned to a user.\n
        `METHOD`: GET
        """

        condition: list[dict] = request.data.get("condition", None)

        condition, exclude_condition = advanced_query_filter(condition)
        roles = RolesUsers.objects.filter(condition)

        for exclude in exclude_condition:
            roles.exclude(**exclude)

        roles = Roles.objects.filter(rol_id__in=roles.values_list("rol_id", flat=True))

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(roles, request)

        serializer = RolesSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)

    @viewException
    def get_department_list(self, request: Request):
        """
        This andpoint accepts a condition with any field in the mode `Department`
        and return all data tha match with the given condition\n
        `METHOD` POST
        """
        condition = dict_key_to_lower(request.data.get("condition", None))
        fields = list_values_to_lower(request.data.get("fields", "__all__"))

        if not condition:
            raise PayloadValidationError("Condition is required")

        departments = Department.objects.filter(simple_query_filter(condition))

        serializer = DynamicSerializer(
            model=Department,
            fields=fields,
            instance=departments,
            many=True,
            context={"request": request},
        )

        return Response({"data": serializer.data})


class MenuOptionsViewSet(ViewSet):
    """
    This viewset provides the following actions:\n
    >> - list: Return a list of menu options.
    >> - create: Create a new menu option.
    >> - update: Update the given menu option.
    >> - delete: Delete the given menu option.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]

    @viewException
    def get_menu_options(self, request):
        """
        Return a list of menu options.\n
        `METHOD`: GET
        """
        user_id = request.user.user_id
        user = User.objects.get(user_id=user_id)
        if not user:
            raise UserDoesNotExist(f"User with id: '{user_id}' was not found.")

        roles = user.roles.all().values_list("rol_id", flat=True)

        user = User.objects.get(user_id=user_id)

        menu_options = MenuOptions.objects.filter(
            Q(Q(menuoptonxroles__rol_id__in=roles) | Q(userpermission__user_id=user))
            & Q(state=MenuOptions.ACTIVE)
            & Q(parent_id__isnull=True)
        ).distinct()

        serializer = MenuOptionsSerializer(
            menu_options, many=True, context={"request": request}
        )
        return Response({"data": serializer.data})
