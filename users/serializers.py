from rest_framework import serializers
from django.db.models import Q

from helpers.serializers import BaseModelSerializer
from payroll.models import DeductionXuser
from users.models import (
    Department,
    MenuOptions,
    OperationsMeneOptions,
    Parameters,
    Roles,
    RolesUsers,
    User,
    UserPermission,
)


class RolesSerializer(BaseModelSerializer):
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop("fields", "__all__")
        self.Meta.fields = fields
        super().__init__(*args, fields=fields, **kwargs)

    class Meta:
        model = Roles


class AuthenticateUserSerializer(BaseModelSerializer):
    """
    Serializer for the authenticate user view.
    """

    roles = serializers.SerializerMethodField()
    session_cookie = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, instance: User):
        return f"{instance.name} {instance.last_name}"

    def get_roles(self, instance: User):
        roles_user = RolesUsers.objects.filter(
            Q(user_id=instance.user_id) & Q(state=RolesUsers.ACTIVE)
        )
        roles = Roles.objects.filter(
            rol_id__in=roles_user.values_list("rol_id", flat=True)
        ).all()
        serializer = RolesSerializer(roles, many=True)
        return [role["NAME"] for role in serializer.data]

    def get_session_cookie(self, _instance: User):
        session_cookie = {
            "token": self.token,
            "expires": self.expires,
        }

        return session_cookie

    def __init__(self, token: str, expires: str = None, **kwargs):
        self.token = token
        self.expires = expires
        super().__init__(**kwargs)

    class Meta:
        model = User
        fields = (
            "user_id",
            "username",
            "email",
            "full_name",
            "roles",
            "avatar",
            "session_cookie",
        )


class UserSerializer(BaseModelSerializer):
    """
    Serializer for the user model.
    """

    roles = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()
    gross_salary = serializers.SerializerMethodField()
    net_salary = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField(source="get_avatar")
    desc_gender = serializers.SerializerMethodField()
    name_supervisor = serializers.SerializerMethodField()
    deductions = serializers.SerializerMethodField(source="get_deductions")
    desc_department = serializers.SerializerMethodField()

    def get_desc_department(self, obj: User):
        if obj.department:
            return obj.department.name
        return None

    def get_deductions(self, obj: User):
        deductions = DeductionXuser.objects.filter(user=obj.username)
        return deductions.values_list("deduction_id", flat=True)

    def get_name_supervisor(self, instance: User | dict):
        if isinstance(instance, User):
            if instance.supervisor:
                supervisor = instance.supervisor
                return f"{supervisor.name} {supervisor.last_name}" or ""
        return ""

    def get_desc_gender(self, instance: User | dict):
        if isinstance(instance, User):
            genders = dict(User.GENDER_CHOICES)
            return genders.get(instance.gender, "")
        return instance.get("gender", "")

    def get_tax(self, instance: User | dict):
        try:
            salary = 0

            if instance.salary == 0:
                return 0

            if isinstance(instance, User):
                salary = float(instance.salary or 0)
            else:
                salary = float(instance.get("salary", 0))
            sfs = salary * 0.0304
            afp = salary * 0.0287
            return sfs + afp
        except ValueError:
            return 0

    def get_net_salary(self, instance: User):
        try:
            if isinstance(instance, User) and instance.salary:
                return float(instance.salary) - self.get_tax(instance)
        except ValueError:
            return 0

    def get_gross_salary(self, instance: User):
        if isinstance(instance, User):
            return instance.salary or 0

    def get_roles(self, instance: User):
        if isinstance(instance, dict):
            return instance.get("roles", [])
        roles_user = RolesUsers.objects.filter(
            Q(user_id=instance.user_id) & Q(state=RolesUsers.ACTIVE)
        )
        roles = Roles.objects.filter(
            rol_id__in=roles_user.values_list("rol_id", flat=True)
        ).all()
        return RolesSerializer(roles, many=True).data

    def get_avatar(self, instance: User):
        if isinstance(instance, dict):
            return instance.get("avatar", "")
        return instance.avatar or instance.username[:2].upper()

    class Meta:
        model = User
        exclude = ("password", "salary")


class UserPermissionSerializer(BaseModelSerializer):
    """
    Serializer for the user permissions.
    """

    class Meta:
        model = UserPermission
        fields = ("operation_id", "user_id")


class MenuOptionsSerializer(BaseModelSerializer):
    """
    Serializer for the menu options.
    """

    label = serializers.CharField(source="name")
    key = serializers.CharField(source="menu_option_id")
    children = serializers.SerializerMethodField()
    title = serializers.CharField(source="description")
    operations = serializers.SerializerMethodField()
    parameters = serializers.SerializerMethodField()

    def get_parameters(self, instance: MenuOptions):
        parameters = instance.parameters.all()
        serializer = ParametersSerializer(parameters, many=True)
        output = {}
        for parameter in serializer.data:
            output[parameter["NAME"]] = parameter["VALUE"]
        return output

    def get_children(self, instance: MenuOptions):
        options = MenuOptions.objects.filter(parent_id=instance.menu_option_id).all()
        return MenuOptionsSerializer(options, many=True).data or None

    def get_operations(self, instance: MenuOptions):
        operations_mene_options = OperationsMeneOptions.objects.filter(
            menu_option_id=instance.menu_option_id
        )
        user_permissions = [
            operation.user_permission_id for operation in operations_mene_options
        ]

        operations = UserPermissionSerializer(user_permissions, many=True).data
        return [operation["OPERATION_ID"] for operation in operations]

    def to_representation(self, instance):
        return serializers.ModelSerializer.to_representation(self, instance)

    class Meta:
        model = MenuOptions
        fields = (
            "label",
            "key",
            "type",
            "title",
            "path",
            "operations",
            "parameters",
            "children",
            "icon",
            "content",
        )


class ParametersSerializer(BaseModelSerializer):
    """
    Serializer for the parameters.
    """

    class Meta:
        model = Parameters
        fields = "__all__"
