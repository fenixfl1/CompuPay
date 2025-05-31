from rest_framework import serializers
from rest_framework.request import Request
from django.db.models import Q

from helpers.serializers import (
    BaseModelSerializer,
    BaseReportModelSerializer,
)
from helpers.utils import currency_format
from payroll.models import DeductionXuser
from users.models import (
    MenuOptions,
    Operations,
    OperationsMeneOptions,
    Parameters,
    ParametersXMenuOptions,
    PermissionsRoles,
    Roles,
    RolesUsers,
    User,
    UserPermission,
    Business,
)


class RolesSerializer(BaseModelSerializer):
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop("fields", "__all__")
        self.Meta.fields = fields
        super().__init__(*args, fields=fields, **kwargs)

    class Meta:
        model = Roles


class BusinessSerializer(BaseModelSerializer):
    """
    Serializer for the business model.
    """

    class Meta:
        model = Business
        fields = "__all__"


class AuthenticateUserSerializer(BaseModelSerializer):
    """
    Serializer for the authenticate user view.
    """

    roles = serializers.SerializerMethodField()
    session_cookie = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    business_id = serializers.SerializerMethodField()

    def get_business_id(self, instance: User):
        business = Business.objects.filter(
            Q(business_id=instance.business_id) & Q(state=Business.ACTIVE)
        ).first()
        if business:
            return business.business_id
        return None

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
            "business_id",
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

    def get_children(self, instance: MenuOptions):
        request: Request = self.context.get("request", None)
        user: User = request.user
        roles = user.roles.all().values_list("rol_id", flat=True)

        user_permissions = UserPermission.objects.filter(
            Q(user_id=user.user_id) & Q(state=UserPermission.ACTIVE)
        ).values_list("id", flat=True)

        operation_menu_options = OperationsMeneOptions.objects.filter(
            Q(user_permission_id__in=user_permissions)
            & Q(state=OperationsMeneOptions.ACTIVE)
        ).values_list("menu_option_id", flat=True)

        menu_options = MenuOptions.objects.filter(
            Q(
                Q(menu_option_id__in=operation_menu_options)
                | Q(menuoptionxroles__rol_id__in=roles)
                | Q(userpermission__user_id=user)
            )
            & Q(state=MenuOptions.ACTIVE)
            & Q(parent_id=instance.menu_option_id)
        ).distinct()

        return (
            MenuOptionsSerializer(
                menu_options,
                many=True,
                context={"request": self.context.get("request", None)},
            ).data
            or None
        )

    def get_parameters(self, instance: MenuOptions):
        children = MenuOptions.objects.filter(parent_id=instance.menu_option_id)
        if children:
            return None

        params_x_menu = ParametersXMenuOptions.objects.filter(
            Q(option_id=instance.menu_option_id)
            & Q(state=ParametersXMenuOptions.ACTIVE)
        ).values_list("parameter_id", flat=True)

        parameters = Parameters.objects.filter(parameter_id__in=params_x_menu)
        serializer = ParametersSerializer(parameters, many=True)
        output = {}

        for parameter in serializer.data:
            output[parameter["NAME"]] = parameter["VALUE"]

        return output

    def get_operations(self, instance: MenuOptions):
        request: Request = self.context.get("request", None)

        operations_mene_options = OperationsMeneOptions.objects.filter(
            Q(menu_option_id=instance.menu_option_id)
            & Q(user_permission_id__user_id=request.user)
            & Q(state=OperationsMeneOptions.ACTIVE)
        ).values_list("user_permission_id__operation_id__operation_id", flat=True)

        roles_id = []
        if request:
            roles_id = User.get_user_roles(request.user.username).values_list(
                "rol_id", flat=True
            )

        operation_x_rol = PermissionsRoles.objects.filter(
            Q(state=PermissionsRoles.ACTIVE) & Q(rol_id__in=roles_id)
        ).values_list("operation_id__operation_id", flat=True)

        operation_ids = set(operation_x_rol).union(operations_mene_options)

        operations = Operations.objects.filter(
            Q(operation_id__in=operation_ids) & Q(state=Operations.ACTIVE)
        ).values_list("operation_id", flat=True)

        return operations

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


class UserReportSerializer(BaseReportModelSerializer):
    """
    Serializer for the user model.
    """

    id = serializers.CharField(source="user_id")
    nombre = serializers.CharField(source="full_name")
    usuario = serializers.CharField(source="username")
    correo = serializers.CharField(source="email")
    # telefono = serializers.SerializerMethodField()
    doc_identidad = serializers.SerializerMethodField()
    rol = serializers.SerializerMethodField()
    salario = serializers.SerializerMethodField()
    # genero = serializers.SerializerMethodField()
    supervisor = serializers.SerializerMethodField()
    departamento = serializers.SerializerMethodField()

    def get_departamento(self, obj: User):
        if obj.department:
            return obj.department.name
        return None

    def get_supervisor(self, instance: User | dict):
        if isinstance(instance, User):
            if instance.supervisor:
                supervisor = instance.supervisor
                return f"{supervisor.name} {supervisor.last_name}" or ""
        return ""

    def get_genero(self, instance: User | dict):
        if isinstance(instance, User):
            genders = dict(User.GENDER_CHOICES)
            return genders.get(instance.gender, "")
        return instance.get("gender", "")

    def get_salario(self, instance: User):
        return currency_format(instance.salary or 0)

    def get_rol(self, instance: User):
        if isinstance(instance, dict):
            return instance.get("roles", [])
        roles_user = RolesUsers.objects.filter(
            Q(user_id=instance.user_id) & Q(state=RolesUsers.ACTIVE)
        )
        role = Roles.objects.filter(
            rol_id__in=roles_user.values_list("rol_id", flat=True)
        ).first()

        if role:
            return role.name

        return ""

    def get_doc_identidad(self, instance: User):
        doc = instance.identity_document
        return f"{doc[:3]}-{doc[3:10]}-{doc[10:]}"

    def get_telefono(self, instance: User):
        phone = instance.phone
        return f"({phone[:3]}) {phone[3:7]}-{phone[7:]}"

    class Meta:
        model = User
        fields = (
            "id",
            "nombre",
            "doc_identidad",
            "usuario",
            "correo",
            # "telefono",
            "rol",
            "salario",
            # "genero",
            "supervisor",
            "departamento",
        )
