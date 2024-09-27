from django import forms

from rest_framework.viewsets import ViewSet
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from helpers.serializers import PaginationSerializer


class BaseProtectedViewSet(ViewSet):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = PaginationSerializer


class BaseModelForm(forms.ModelForm):
    """
    Este es un formulario base para todos los formularios en el panel de administración.
    """

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        if self.request and hasattr(self.request, "user"):
            self.fields["created_by"].initial = self.request.user

    def save(self, commit=True):
        if self.instance.pk is None and self.request and hasattr(self.request, "user"):
            self.instance.created_by = self.request.user
        return super().save(commit=commit)
