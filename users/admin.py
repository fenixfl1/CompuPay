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
    MenuOptions,
    Operations,
    OperationsMeneOptions,
    Parameters,
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
    list_filter = ("is_staff", "is_superuser")
    list_display = (
        "user_id",
        "render_avatar",
        "get_full_name",
        "username",
        "get_roles_name",
        "email",
        "is_staff",
        "is_superuser",
        "state",
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


admin.site.register(User, UserAdmin)
admin.site.register(MenuOptions, MenuOptionAdmin)
admin.site.register(Roles, RolesAdmin)
admin.site.register(Operations, OperationsAdmin)
admin.site.register(UserPermission, UserPermissionAdmin)
admin.site.register(OperationsMeneOptions, OperationsMeneOptionsAdmin)
admin.site.register(RolesUsers, RolesUserAdmin)
admin.site.register(Parameters, ParametesAdmin)
