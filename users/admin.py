from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from helpers.admin import BaseModelAdmin, BaseModelInline
from users.forms import (
    CustomCreationForm,
    CustomUserChangeForm,
    OperationsMeneOptionsForm,
    UstomAuthForm,
)
from users.models import (
    ActivityLog,
    Department,
    MenuOptions,
    MenuOptonXroles,
    Operations,
    OperationsMeneOptions,
    Parameters,
    ParametesXmenuOptions,
    PermissionsRoles,
    Roles,
    RolesUsers,
    User,
    UserPermission,
)


class UserAdmin(BaseModelAdmin):
    """
    Custom user admin model for the admin site
    """

    add_form = CustomCreationForm
    login_form = UstomAuthForm
    model = User
    form = CustomUserChangeForm

    ordering = ("user_id",)
    display_name = "username"
    list_filter = ("is_staff", "is_superuser", "department")
    list_display = (
        "user_id",
        "render_avatar",
        "full_name",
        "username",
        "identity_document",
        "get_roles_name",
        "email",
        "department",
        "salary",
        "is_staff",
        "is_superuser",
        "state",
    )
    list_editable = (
        "department",
        "is_staff",
        "is_superuser",
        "salary",
    )

    filter_horizontal = ()

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "username",
                    "avatar",
                    "is_superuser",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login",)}),
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
    list_filter = ("state",)


class PermissionsRolesInline(BaseModelInline):
    model = PermissionsRoles
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


class ParametesAdmin(BaseModelAdmin):
    list_display = (
        "parameter_id",
        "name",
        "description",
        "value",
    )
    list_filter = ("state",)


class ParametesXmenuOptionsAdmin(BaseModelAdmin):
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


class MenuOptionXrolesAdmin(BaseModelAdmin):
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


admin.site.register(User, UserAdmin)
admin.site.register(MenuOptions, MenuOptionAdmin)
admin.site.register(Roles, RolesAdmin)
admin.site.register(Operations, OperationsAdmin)
admin.site.register(UserPermission, UserPermissionAdmin)
admin.site.register(OperationsMeneOptions, OperationsMeneOptionsAdmin)
admin.site.register(RolesUsers, RolesUserAdmin)
admin.site.register(Parameters, ParametesAdmin)
admin.site.register(ParametesXmenuOptions, ParametesXmenuOptionsAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(PermissionsRoles, PermissionsRolesAdmin)
admin.site.register(MenuOptonXroles, MenuOptionXrolesAdmin)
admin.site.register(ActivityLog, ActivityLogAdmin)
