from django.db import connection
from django.urls import reverse
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.contrib.admin.sites import AdminSite

from users.models import STATE_CHOICES


class BaseModelAdmin(admin.ModelAdmin):
    def __init__(
        self, model, admin_site: AdminSite | None, state_field="state"
    ) -> None:
        super().__init__(model, admin_site)
        self.list_display = self.list_display + (
            state_field,
            "edit_link",
        )
        self.list_editable = self.list_editable + (state_field,)
        if self.exclude is None:
            self.exclude = ()
        self.exclude = self.exclude + ("updated_at", "updated_by")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            obj.created_at = timezone.now()
            obj.pk = self.model.objects.count() + 1

        else:  # Si es una instancia existente
            obj.updated_by = request.user
        obj.save()
        super().save_model(request, obj, form, change)

    def edit_link(self, obj) -> str:
        if obj.pk:
            url = reverse(
                f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
                args=[obj.pk],
            )
            return format_html('<a href="{}">Editar</a>', url)
        return ""

    edit_link.short_description = "Editar"


class BaseModelInline(admin.TabularInline):
    def __init__(self, parent_model, admin_site, state_field="state") -> None:
        self.state_field = state_field
        super().__init__(parent_model, admin_site)
        if self.exclude is None:
            self.exclude = ()
        self.exclude = self.exclude + ("updated_at", "updated_by")
        self.extra = 1
        self.max_num = 10
        self.show_change_link = True
        self.readonly_fields = (self.state_field,)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            obj.created_at = timezone.now()
        else:
            obj.updated_by = request.user
        obj.save()
        # pylint: disable=no-member
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        return request.user.is_authenticated

    def has_permission(self, request, _obj=None):
        return request.user.is_authenticated
