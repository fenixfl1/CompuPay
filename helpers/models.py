from datetime import datetime
from typing import Self

from django.db import models
from django.utils import timezone

from rest_framework.request import Request
from rest_framework.exceptions import APIException


STATE_CHOICES = (
    ("A", "Activo"),
    ("I", "Inactivo"),
)


class ModelManager(models.Manager):
    pass


class BaseModels(models.Model):
    """
    Base model for all models in the project.
    """

    ACTIVE = "A"
    INACTIVE = "I"
    STATE_CHOICES = STATE_CHOICES

    state = models.CharField(
        default="A", max_length=1, null=False, choices=STATE_CHOICES
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        to_field="username",
        related_name="%(class)s_created_by",
        db_column="created_by",
    )
    updated_by = models.ForeignKey(
        "users.User",
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

    objects = ModelManager()

    @classmethod
    def create(cls, request: Request, **kwargs):
        try:
            kwargs["created_by"] = request.user
            kwargs["created_at"] = datetime.now()

            allowed_states = dict(STATE_CHOICES)

            if kwargs["state"] not in allowed_states:
                raise APIException(
                    f"`STATE` must be one of the following values: {allowed_states}"
                )

            # pylint: disable=no-member
            return cls.objects.create(**kwargs)
        except Exception as e:
            raise APIException(e) from e

    @classmethod
    def update(cls, request: Request, instance: Self, **kwargs):
        try:
            # pylint: disable=no-member
            allowed_states = dict(cls.STATE_CHOICES)

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

    class Meta:
        abstract = True
