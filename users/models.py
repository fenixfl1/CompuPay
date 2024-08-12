from datetime import datetime
from django.db import models
from django.forms import ValidationError
from django.utils import timezone
from django.utils.html import format_html
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from rest_framework.exceptions import APIException
from rest_framework.request import Request

from helpers.exceptions import UserDoesNotExist

STATE_CHOICES = (
    ("A", "Activo"),
    ("I", "Inactivo"),
)


class ModelManager(models.Manager):
    pass


class UserManager(BaseUserManager):
    def create_user(
        self,
        name: str,
        last_name: str,
        email: str,
        username: str,
        password: str,
        created_by: "User" = None,
        **extra_fields,
    ) -> "User":
        try:
            if not email:
                raise ValueError("The Email is required")
            email = self.normalize_email(email)

            roles = extra_fields.pop("roles", None)

            user = self.model(
                name=name,
                last_name=last_name,
                email=email,
                username=username,
                created_by=created_by,
                created_at=datetime.now(),
                **extra_fields,
            )

            user.set_password(password)
            user.save(using=self._db)

            if roles is not None:
                roles_users = []
                roles = Roles.objects.filter(rol_id__in=roles)

                for role in roles:
                    roles_users.append(
                        RolesUsers(rol_id=role, user_id=user, created_by=created_by)
                    )

                RolesUsers.objects.bulk_create(roles_users)

            return user
        except Exception as e:
            raise APIException(e) from e

    def create_superuser(
        self,
        name: str,
        last_name: str,
        email: str,
        username: str,
        password: str,
        created_by: "User"  = None,
        **extra_fields,
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(
            name=name,
            last_name=last_name,
            email=email,
            username=username,
            password=password,
            created_by=created_by,
            **extra_fields,
        )


class User(AbstractBaseUser):
    GENDER_CHOICES = ("M", "Masculino"), ("F", "Femenino")
    STATE_CHOICES = (
        ("A", "Activo"),
        ("I", "Inactivo"),
        ("D", "Despidido"),
        ("R", "Renunciado"),
        ("P", "Pendiente"),
        ("E", "Evaluado"),
        ("J", "Rechazado"),
    )

    user_id = models.AutoField(primary_key=True)
    identity_document = models.CharField(max_length=20, blank=False, null=False)
    document_type = models.CharField(
        max_length=2,
        blank=False,
        null=False,
        choices=[("C", "Cedula"), ("P", "Pasaporte")],
    )
    name = models.CharField(max_length=100, blank=False, null=False)
    last_name = models.CharField(max_length=100, blank=False, null=False)
    email = models.EmailField(max_length=100, blank=False, null=False)
    password = models.CharField(max_length=100, blank=False, null=False)
    username = models.CharField(max_length=100, blank=False, null=False, unique=True)
    phone = models.CharField(max_length=20)
    hired_date = models.DateField(blank=True, null=True)
    contract_end = models.DateField(blank=True, null=True)
    currency = models.CharField(
        max_length=3,
        blank=False,
        null=False,
        default="RD",
        choices=[("RD", "RD"), ("USD", "USD"), ("EUR", "EUR")],
    )
    salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    updated_at = models.DateTimeField(null=True, blank=True)
    gender = models.CharField(max_length=1, blank=False, null=False, default="M", choices=GENDER_CHOICES)
    birth_date = models.DateField(blank=True, null=True)
    state = models.CharField(
        default="A", max_length=1, null=False, choices=STATE_CHOICES
    )
    avatar = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    resume = models.TextField(null=True, blank=True)
    supervisor = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        to_field="username",
        related_name="%(class)s_supervisor",
        null=True,
        blank=True,
        db_column="supervisor",
    )
    created_by = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        to_field="username",
        related_name="%(class)s_created_by",
        null=True,
        blank=True,
        db_column="created_by",
    )
    updated_by = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        to_field="username",
        related_name="%(class)s_updated_by",
        null=True,
        blank=True,
        db_column="updated_by",
    )
    roles = models.ManyToManyField(
        "Roles",
        through="RolesUsers",
        through_fields=("user_id", "rol_id"),
        related_name="%(class)s_roles",
    )

    objects = UserManager()

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"

    ACTIVE = "A"
    INACTIVE = "I"

    REQUIRED_FIELDS= [
        "identity_document",
        "document_type",
        "name",
        "last_name",
        "email",
        "password",
    ]

    NON_UPDATEABLE_FIELDS = [
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "identity_document",
        "username",
    ]

    def __str__(self):
        return f"@{self.username}"

    def has_perm(self, _app_label: str) -> bool:
        return self.is_staff or self.is_superuser

    def has_module_perms(self, _app_label: str) -> bool:
        return self.is_staff or self.is_superuser

    @classmethod
    def update_user(cls, request: Request, user_id: int, **kwargs) -> "User":
        try:
            user = cls.objects.get(user_id=user_id)
            for key, value in kwargs.items():
                setattr(user, key, value)
            user.updated_at = datetime.now()
            user.updated_by = request.user
            user.save()
            return user
        except UserDoesNotExist as e:
            raise APIException(e.message) from e

    def get_full_name(self) -> str:
        return f"{self.name} {self.last_name}"

    def get_roles_name(self) -> str:
        roles = RolesUsers.objects.filter(user_id=self, state=self.ACTIVE).values_list(
            "rol_id__name", flat=True
        )

        return ", ".join(roles)

    def render_avatar(self):
        if self.avatar:
            return format_html(
                f'<img src="{self.avatar}" width="60" height="60" style="border-radius: 50%;" />'
            )
        return ""

    render_avatar.short_description = "Avatar"
    get_full_name.short_description = "Name"
    get_roles_name.short_description = "Roles"

    class Meta:
        db_table = "USERS"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["user_id"]


class BaseUsersModels(models.Model):
    state = models.CharField(
        default="A", max_length=1, null=False, choices=STATE_CHOICES
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        to_field="username",
        related_name="%(class)s_created_by",
        db_column="created_by",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        to_field="username",
        related_name="%(class)s_updated_by",
        null=True,
        blank=True,
        db_column="updated_by",
    )

    NON_UPDATEABLE_FIELDS = [
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]

    @classmethod
    def create(cls, request, **kwargs):
        try:
            kwargs["created_by"] = request.user
            kwargs["created_at"] = datetime.now()

            allowed_states = dict(STATE_CHOICES)

            if kwargs["state"] not in allowed_states:
                raise APIException(
                    f"`STATE` must be one of the following values: {allowed_states}"
                )

            return cls.objects.create(**kwargs)
        except Exception as e:
            raise APIException(e) from e

    @classmethod
    def update(cls, request, instance, **kwargs):
        try:
            allowed_states = dict(STATE_CHOICES)

            if kwargs.get("state", None) and kwargs["state"] not in allowed_states:
                raise APIException(
                    f"`STATE` must be one of the following values: {allowed_states}"
                )

            non_updateable_fields = [
                field for field in kwargs if field.lower() in cls.NON_UPDATEABLE_FIELDS
            ]
            if non_updateable_fields:
                raise APIException(
                    "NON-UPDATEABLE FIELD(s): " + ", ".join(non_updateable_fields)
                )

            kwargs["updated_by"] = request.user
            kwargs["updated_at"] = timezone.now()

            # Update each field in kwargs
            for field, value in kwargs.items():
                setattr(instance, field, value)

            # Save the updated object
            instance.save()

            return instance

        except Exception as e:
            raise APIException(str(e)) from e

    objects = ModelManager()

    ACTIVE = "A"
    INACTIVE = "I"

    class Meta:
        abstract = True


class Operations(BaseUsersModels):
    """
    This model represents the permissions.
    `TABLE NAME`: OPERATIONS
    """

    operation_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, null=False, unique=True)
    description = models.CharField(max_length=100, null=True, blank=True)

    REQUIRED_FIELDS = ["name", "created_by", "state"]
    ALLOWED_FIELDS = REQUIRED_FIELDS + ["description"]

    def __str__(self):
        return f"{self.name}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    class Meta:
        db_table = "OPERATIONS"
        verbose_name = "Operacion"
        verbose_name_plural = "Operaciones"
        ordering = ["operation_id"]


class Roles(BaseUsersModels):
    """
    This model represents the roles.
    `TABLE NAME`: ROLES
    """

    rol_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=25, null=False, unique=True)
    description = models.CharField(max_length=200)
    init_user_state = models.CharField(
        max_length=1, choices=User.STATE_CHOICES, default="A"
    )
    color = models.CharField(max_length=7, default="#000000")
    operations = models.ManyToManyField(
        Operations,
        through="PermissionsRoles",
        through_fields=("rol_id", "operation_id"),
        related_name="%(class)s_roles",
    )

    REQUIRED_FIELDS = ["name", "created_by"]
    ALLOWED_FIELDS = [
        "name",
        "description",
        "state",
        "created_by",
    ]

    def __str__(self):
        return f"{self.name}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def render_color(self):
        return format_html(
            f'<span style="padding: 5px; border-radius: 5px; background-color: {self.color}; font-weight: bold; height: 50px;width: 100px;min-width: 180px">{self.color}</span>'
        )

    render_color.short_description = "Color"

    class Meta:
        db_table = "ROLES"
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ["rol_id"]


class RolesUsers(BaseUsersModels):
    rol_id = models.ForeignKey(
        Roles, on_delete=models.CASCADE, null=False, db_column="rol_id"
    )
    user_id = models.ForeignKey(
        User, on_delete=models.CASCADE, null=False, db_column="user_id"
    )

    def __repr__(self) -> str:
        return f"{self.rol_id}"

    def __str__(self) -> str:
        return f"Role: {self.rol_id}, User: {self.user_id}"

    def get_username(self):
        return f"@{self.user_id.username}"

    def get_rol_name(self):
        return self.rol_id.name

    get_username.short_description = "Username"
    get_rol_name.short_description = "Role"

    class Meta:
        db_table = "ROLES_X_USERS"
        verbose_name = "Rol por usuario"
        verbose_name_plural = "Roles por usuarios"
        constraints = [
            models.UniqueConstraint(fields=["rol_id", "user_id"], name="pk_rol_usuario")
        ]


class MenuOptions(BaseUsersModels):
    """
    This model represents the menu options.\n
    `TABLE NAME`: MENU_OPTIONS
    """

    menu_option_id = models.CharField(
        primary_key=True, null=False, blank=False, max_length=10
    )
    name = models.CharField(max_length=100, null=False, blank=False)
    description = models.CharField(max_length=250, null=True, blank=True)
    path = models.CharField(max_length=100, null=True, blank=True)
    type = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=[("group", "Group"), ("divider", "Divider")],
    )
    icon = models.TextField(null=True, blank=True)
    parent_id = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        to_field="menu_option_id",
        related_name="%(class)s_parent_id",
        null=True,
        blank=True,
        db_column="parent_id",
    )
    order = models.IntegerField(null=False, blank=False)
    parameters = models.ManyToManyField("Parameters", blank=True)

    REQUIRED_FIELDS = [
        "description",
        "menu_option_id",
        "name",
        "state",
    ]
    ALLOWED_FIELDS = REQUIRED_FIELDS + [
        "order",
        "parent_id",
        "state",
    ]

    def __str__(self) -> str:
        return f"{self.name}. {self.description}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def get_parent_name(self):
        return self.parent_id.name if self.parent_id else ""

    def normalize_icon(self):
        return format_html(f"{self.icon}")

    get_parent_name.short_description = "Parent"
    normalize_icon.short_description = "Icon"

    def clean(self):
        super().clean()
        if self.parent_id:
            siblings = MenuOptions.objects.filter(parent_id=self.parent_id).exclude(
                pk=self.pk
            )
            orders = [sibling.order for sibling in siblings]
            if self.order in orders:
                raise ValidationError(
                    f"Order {self.order} already exists for the given parent_id."
                )
            if not 0 <= self.order < len(siblings) + 1:
                raise ValidationError(
                    f"Order must be between 0 and {len(siblings)} for the given parent_id."
                )

    class Meta:
        db_table = "MENU_OPTIONS"
        verbose_name = "Opción de Menú"
        verbose_name_plural = "Opciones de Menú"
        ordering = ["order", "menu_option_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent_id", "order"], name="unique_order_per_parent"
            )
        ]


class OperationsMeneOptions(BaseUsersModels):
    """
    This model represents the permission for each user on each menu option.\n
    This model is an intemediary model between `UserPermission` and `MenuOptions`.\n
    `TABLE NAME:` OPERATIONS_X_MENU_OPTIONS
    """

    user_permission_id = models.ForeignKey(
        "UserPermission",
        on_delete=models.CASCADE,
        null=False,
        db_column="user_permission_id",
    )
    menu_option_id = models.ForeignKey(
        MenuOptions, on_delete=models.CASCADE, null=False, db_column="menu_option_id"
    )

    def __str__(self) -> str:
        return (
            f"Operation: {self.user_permission_id}, Menu Option: {self.menu_option_id}"
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.user_permission_id!r})"

    def get_operation_name(self):
        # pylint: disable=no-member
        return self.user_permission_id.operation_id.name.upper()

    def get_username(self):
        return f"@{self.user_permission_id.user_id.username}"

    def get_menu_option(self):
        return self.menu_option_id.name

    get_operation_name.short_description = "Operation"
    get_username.short_description = "Username"
    get_menu_option.short_description = "Menu option"

    class Meta:
        db_table = "OPERATIONS_X_MENU_OPTIONS"
        verbose_name = "Operacione por opción de menú"
        verbose_name_plural = "Operaciones por opciones de menú"
        constraints = [
            models.UniqueConstraint(
                fields=["user_permission_id", "menu_option_id"],
                name="pk_operation_menu_options",
            )
        ]


class UserPermission(BaseUsersModels):
    """
    This model represents the permissions.\n
    Specify the permissions for each user.\n
    Example:
        > User A can create a new user.\n
        > User B can delete a user.\n
        > User C can update a user.\n
    The user must specify which menu options the user has those permissions on
    through the `OperationsMeneOptions` model.\n
    `TABLE NAME`: PERMISSIONS_X_USERS
    """

    operation_id = models.ForeignKey(
        Operations, on_delete=models.CASCADE, null=False, db_column="operation_id"
    )
    user_id = models.ForeignKey(
        User, on_delete=models.CASCADE, null=False, db_column="user_id"
    )
    menu_options = models.ManyToManyField(MenuOptions, through="OperationsMeneOptions")

    ALLOWED_FIELDS = ["operation_id", "user_id", "state"]
    REQUIRED_FIELDS = ALLOWED_FIELDS

    def __str__(self) -> str:
        return f"Operation: {self.operation_id}, User: {self.user_id}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.operation_id!r})"

    def get_operation_name(self):
        # pylint: disable=no-member
        return self.operation_id.name.upper()

    def get_username(self):
        return f"@{self.user_id.username}"

    def get_menu_option(self):
        # pylint: disable=no-member
        return ", ".join([p.name for p in self.menu_options.all()])

    get_operation_name.short_description = "Operation"
    get_username.short_description = "Username"
    get_menu_option.short_description = "Menu options"

    class Meta:
        db_table = "PERMISSIONS_X_USERS"
        verbose_name = "Permiso de username"
        verbose_name_plural = "Permisos de usuarios"
        constraints = [
            models.UniqueConstraint(
                fields=["operation_id", "user_id"],
                name="unique_user_permission",
            )
        ]


class PermissionsRoles(BaseUsersModels):
    """
    This model represents the relationship between Roles and permissions
    `TABLE NAME:` PERMISSIONS_X_ROLES
    """

    operation_id = models.ForeignKey(
        Operations, on_delete=models.CASCADE, null=False, db_column="operation_id"
    )

    rol_id = models.ForeignKey(
        Roles, on_delete=models.CASCADE, null=False, db_column="rol_id"
    )

    def __repr__(self) -> str:
        return f"{self.operation_id}"

    def __str__(self) -> str:
        return f"Operation: {self.operation_id}, Role: {self.rol_id}"

    class Meta:
        db_table = "PERMISSIONS_X_ROLES"
        verbose_name = "Permisio por rol"
        verbose_name_plural = "Permisios por roles"


class Parameters(BaseUsersModels):
    """
    This model represents the parameters.\n
    `TABLE NAME`: PARAMETERS
    """

    parameter_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, null=False, blank=False, unique=True)
    value = models.TextField(null=False, blank=False)
    description = models.CharField(max_length=250, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    class Meta:
        db_table = "PARAMETERS"
        verbose_name = "Parametro"
        verbose_name_plural = "Parametros"
        ordering = ["parameter_id"]
