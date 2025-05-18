from django.contrib import admin, messages
from django.contrib.admin.sites import AdminSite
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html
from helpers.admin import BaseModelAdmin, BaseModelInline
from users.forms import (
    CustomCreationForm,
    CustomUserChangeForm,
    OperationsMeneOptionsForm,
    CustomAuthForm,
)
from users.models import (
    ActivityLog,
    Bank,
    BankAccount,
    Business,
    Department,
    MenuOptions,
    MenuOptionXRoles,
    Operations,
    OperationsMeneOptions,
    Parameters,
    ParametersXMenuOptions,
    PermissionsRoles,
    Roles,
    RolesUsers,
    Termination,
    User,
    UserPermission,
)


def reset_password(request, user_id):
    try:
        print("*" * 75)
        print(f"User: {user_id} \n Request: {request}")
        print("*" * 75)
        user = User.objects.get(user_id=user_id)
        default_password = Parameters.objects.get(name="DEFAULT_PASSWORD").value

        if not default_password:
            messages.error(
                request,
                "No se encontró una contraseña por defecto en los parámetros.",
            )
            return redirect(request.META.get("HTTP_REFERER", ".."))

        user.set_password(default_password)
        user.save()

        messages.success(
            request,
            f"La contraseña del usuario {user.username} ha sido restablecida a la contraseña por defecto.",
        )
    except User.DoesNotExist:
        messages.error(request, "El usuario no existe.")
    # pylint: disable=broad-exception-caught
    except Exception as e:
        messages.error(request, f"Error al restablecer la contraseña: {e}")
    return redirect(request.META.get("HTTP_REFERER", ".."))


class RoleUserInline(admin.TabularInline):
    model = RolesUsers
    fk_name = "user_id"
    fields = ("rol_id", "created_by")
    verbose_name = "Asignación de Rol"
    verbose_name_plural = "Asignaciones de Roles"
    extra = 1


class UserAdmin(BaseModelAdmin):
    """
    Custom user admin model for the admin site
    """

    # add_form = CustomCreationForm
    login_form = CustomAuthForm
    model = User

    inlines = [RoleUserInline]

    ordering = ("user_id",)
    display_name = "username"
    list_filter = ("is_staff", "is_superuser", "department")
    list_display = (
        "user_id",
        "business_id",
        "render_avatar",
        "full_name",
        "username",
        "get_roles_name",
        "email",
        "department",
        "salary",
        "is_staff",
        "is_superuser",
        "state",
        "reset_password",
    )
    list_editable = (
        "department",
        "is_staff",
        "is_superuser",
        "salary",
    )

    filter_horizontal = ()

    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        (
            "Información Personal",
            {
                "fields": (
                    "name",
                    "last_name",
                    "avatar",
                    "is_superuser",
                    "is_staff",
                    "created_by",
                ),
            },
        ),
        (
            "Información laboral",
            {"fields": ("department", "supervisor", "salary")},
        ),
    )

    list_editable = ("is_staff", "is_superuser", "state")

    def has_module_permission(self, request):
        return request.user.is_authenticated

    def has_permission(self, request, _obj=None):
        return request.user.is_authenticated

    def get_state(self, obj):
        states = dict(User.STATE_CHOICES)
        return f"{states[obj.state]}"

    get_state.short_description = "Estado"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:user_id>/reset-password/",
                self.admin_site.admin_view(reset_password),
                name="reset_password",
            ),
        ]
        return custom_urls + urls

    def reset_password(self, obj: User):
        return format_html(
            '<a class="button" href="{}">Restablecer Contraseña</a>',
            reverse("admin:reset_password", args=[obj.pk]),
        )

    reset_password.short_description = "Restablecer contraseña"
    reset_password.allow_tags = True

    def __init__(
        self, model: type, admin_site: AdminSite | None, state_field="is_active"
    ) -> None:
        super().__init__(model, admin_site, state_field)


class MenuOptionAdmin(BaseModelAdmin):
    list_display = (
        "menu_option_id",
        "order",
        "normalize_icon",
        "name",
        "description",
        "type",
        "path",
        "get_parent_name",
    )
    list_filter = ("state",)
    exclude = ("menu_option_id",)

    def save_model(self, request, obj, form, change):
        # Sobrescribimos el menu_option_id si no está presente
        if not obj.menu_option_id:
            if obj.parent_id:
                # Si tiene un padre, genera un ID basado en el ID del padre y un número secuencial
                parent_id = obj.parent_id.menu_option_id
                count_siblings = (
                    MenuOptions.objects.filter(parent_id=obj.parent_id).count() + 1
                )
                obj.menu_option_id = f"{parent_id}-{count_siblings}"
            else:
                # Si no tiene padre, genera un ID secuencial
                count_options = (
                    MenuOptions.objects.filter(parent_id__isnull=True).count() + 1
                )
                obj.menu_option_id = str(count_options)

        # Llamamos al método save_model original para guardar el objeto
        super().save_model(request, obj, form, change)


class PermissionsRolesAdmin(BaseModelAdmin):
    list_display = ("operation_id", "rol_id")
    list_filter = ("state", "rol_id")


class PermissionsRolesInline(BaseModelInline):
    model = PermissionsRoles
    extra = 1


class ParameterMenuOptionInline(BaseModelInline):
    model = ParametersXMenuOptions
    extra = 1


class RolesAdmin(BaseModelAdmin):
    list_display = ("rol_id", "name", "description", "render_color")
    list_filter = ("state",)

    inlines = [PermissionsRolesInline]

    def save_model(self, request, obj, form, change):
        # Aquí puedes agregar tu lógica personalizada antes de guardar
        if not change:  # Si es una nueva instancia
            obj.created_by = request.user
            obj.rol_id = Roles.objects.count() + 1
        else:  # Si es una instancia existente
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class OperationsAdmin(BaseModelAdmin):
    list_display = (
        "operation_id",
        "name",
        "description",
    )
    list_filter = ("state",)

    inlines = [PermissionsRolesInline]


class OperationsMeneOptionsInline(BaseModelInline):
    model = OperationsMeneOptions
    extra = 1
    form = OperationsMeneOptionsForm


class UserPermissionAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "get_operation_name",
        "get_username",
        "get_menu_option",
    )
    list_filter = ("state",)
    inlines = [OperationsMeneOptionsInline]


class OperationsMeneOptionsAdmin(BaseModelAdmin):
    list_display = ("get_operation_name", "get_username", "get_menu_option")
    list_filter = ("state", "menu_option_id")

    form = OperationsMeneOptionsForm


class RolesUserAdmin(BaseModelAdmin):
    list_display = ("rol_id", "user_id")
    list_filter = ("state",)


class ParametersAdmin(BaseModelAdmin):
    list_display = (
        "parameter_id",
        "name",
        "description",
        "value",
    )
    list_filter = ("state",)
    search_fields = ("name", "parameter_id")

    inlines = [ParameterMenuOptionInline]


class ParametersXMenuOptionsAdmin(BaseModelAdmin):
    list_display = (
        "parameter_id",
        "option_id",
    )
    list_filter = ("state",)


class DepartmentAdmin(BaseModelAdmin):
    list_display = (
        "department_id",
        "name",
        "description",
    )
    list_filter = ("state",)


class MenuOptionXRolesAdmin(BaseModelAdmin):
    list_display = (
        "get_rol_name",
        "get_option_name",
    )
    list_filter = ("state", "rol_id")


class ActivityLogAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "action_time",
        "object_repr",
        "get_action_flag_display",
        "content_type_id",
        "username",
        "change_message",
    ]
    list_filter = ["username"]


class BusinessAdmin(BaseModelAdmin):
    list_display = ("business_id", "name", "rnc", "display_representative")


class TerminationAdmin(BaseModelAdmin):
    list_display = (
        "termination_id",
        "username",
        "termination_type",
        "reason",
        "termination_date",
    )


class BankAccountAdmin(BaseModelAdmin):
    list_display = ("username", "no_account", "bank", "account_type", "is_primary")


class BankAdmin(BaseModelAdmin):
    list_display = ("bank_id", "short_name", "name")


admin.site.register(User, UserAdmin)
admin.site.register(MenuOptions, MenuOptionAdmin)
admin.site.register(Roles, RolesAdmin)
admin.site.register(Operations, OperationsAdmin)
admin.site.register(UserPermission, UserPermissionAdmin)
admin.site.register(OperationsMeneOptions, OperationsMeneOptionsAdmin)
admin.site.register(RolesUsers, RolesUserAdmin)
admin.site.register(Parameters, ParametersAdmin)
admin.site.register(ParametersXMenuOptions, ParametersXMenuOptionsAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(PermissionsRoles, PermissionsRolesAdmin)
admin.site.register(MenuOptionXRoles, MenuOptionXRolesAdmin)
admin.site.register(ActivityLog, ActivityLogAdmin)
admin.site.register(Business, BusinessAdmin)
admin.site.register(Termination, TerminationAdmin)
admin.site.register(BankAccount, BankAccountAdmin)
admin.site.register(Bank, BankAdmin)
