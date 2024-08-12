from typing import Any
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    UserChangeForm,
)


from users.models import MenuOptions, OperationsMeneOptions, UserPermission


class UstomAuthForm(AuthenticationForm):
    def confirm_login_allowed(self, user: AbstractBaseUser):
        if not user.state:
            raise forms.ValidationError(
                self.error_messages["inactive"],
                code="inactive",
            )

    fields = ("username", "password")


class CustomCreationForm(UserCreationForm):
    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        help_text=_("Enter the same password as before, for verification."),
    )

    class Meta(UserCreationForm):
        model = get_user_model()
        fields = (
            "email",
            "username",
            "avatar",
            "is_staff",
            "is_superuser",
        )


class CustomUserChangeForm(UserChangeForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        if "created_at" in self.fields:
            # Personaliza el campo 'created_at' aquí si es necesario
            pass

    class Meta:
        model = get_user_model()
        fields = "__all__"


class OperationsMeneOptionsForm(forms.ModelForm):
    class Meta:
        model = OperationsMeneOptions
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        menu_option: MenuOptions = cleaned_data.get("menu_option_id")
        user_permission: UserPermission = cleaned_data.get("user_permission_id")

        # Lista de operaciones de solo lectura
        readonly_operations = ["view", "ver", "solo lectura", "read", "readonly"]

        # Obtener el tipo de operación de la UserPermission
        operation_type = user_permission.get_operation_name().lower()

        # Verificar si la opción de menú es de solo lectura
        if menu_option and menu_option.type:
            if (
                menu_option.type.strip() != ""
                and operation_type not in readonly_operations
            ):
                raise ValidationError(
                    "Cannot assign non-read-only operations to read-only menu options."
                )

        return cleaned_data

    # rewritte the create method
    def create(self, validated_data):
        # count the number of operations
        operations_count = self.Meta.model.objects.all().values_list(
            "operation_id", flat=True
        )
        max_operation_id = max(operations_count) if operations_count else 0
        validated_data["operation_id"] = max_operation_id + 1
        return self.Meta.model.objects.create(**validated_data)
