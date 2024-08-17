import datetime
from django.contrib.auth import authenticate, get_user_model
from django.forms.models import model_to_dict
from django.db.models import Q, Max
from rest_framework.exceptions import APIException, NotFound
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated

from helpers.exceptions import UserDoesNotExist, UserException, viewException
from helpers.serializers import PaginationSerializer
from helpers.utils import advanced_query_filter, dict_key_to_lower, simple_query_filter
from users.models import (
    STATE_CHOICES,
    MenuOptions,
    OperationsMeneOptions,
    PermissionsRoles,
    Roles,
    RolesUsers,
    User,
    UserPermission,
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
    def get_list_users(self, request):
        """
        Return a list of users.\n
        `METHOD`: POST
        """
        conditions: list[dict] = request.data.get("condition", None)

        if not conditions:
            raise APIException("The condition are required")
        if not isinstance(conditions, list):
            raise APIException("Invalid condition")

        condition, exclude_condition = advanced_query_filter(conditions)

        users = User.objects.filter(condition)

        for exclude in exclude_condition:
            users = users.exclude(**exclude)

        paginator = PaginationSerializer(request=request)
        page = paginator.paginate_queryset(users.distinct(), request)

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

        user = User.objects.create_user(**data)

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

        return Response({"message": "User state changed successfully."})

    def update_user(self, request):
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

        user = User.update_user(request, **data)

        if roles:
            try:
                roles_users = RolesUsers.objects.filter(user_id=user)
                if roles_users:
                    roles_users.update(state=RolesUsers.INACTIVE)
                for role in roles:
                    RolesUsers.create(
                        request, user_id=user, rol_id=role, state=RolesUsers.ACTIVE
                    )
            # pylint: disable=broad-except
            except Exception:
                return Response(
                    {
                        "message": "User updated successfully. But an error occurred while assigning roles."
                    },
                    status=400,
                )

        data = model_to_dict(user)

        serializer = UserSerializer(user, data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        return Response(
            {"data": serializer.data, "message": "User updated successfully."}
        )

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
        RolesUsers.create(request, user_id=user, rol_id=rol, state="A")

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

        RolesUsers.create(request, user_id=user, rol_id=role, state=RolesUsers.ACTIVE)

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

        RolesUsers.update(
            request,
            roles_users,
            rol_id=role,
            user_id=user,
            state=RolesUsers.INACTIVE,
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

        user_permissions = UserPermission.objects.filter(
            Q(user_id=user_id) & Q(state=UserPermission.ACTIVE)
        ).values_list("id", flat=True)

        opration_menu_options = OperationsMeneOptions.objects.filter(
            Q(user_permission_id__in=user_permissions)
            & Q(state=OperationsMeneOptions.ACTIVE)
        ).values_list("menu_option_id", flat=True)

        menu_options = MenuOptions.objects.filter(
            Q(menu_option_id__in=opration_menu_options) & Q(state=MenuOptions.ACTIVE)
        )

        serializer = MenuOptionsSerializer(menu_options, many=True)

        return Response({"data": serializer.data})
