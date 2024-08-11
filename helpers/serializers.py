from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination, InvalidPage
from rest_framework.exceptions import NotFound, APIException, ValidationError


class BaseModelSerializer(serializers.ModelSerializer):
    """
    This is the base serializer for all the serializers in the project.
    It includes a method to convert the keys of the dictionary to uppercase.
    """

    def __init__(self, instance=None, data=None, fields=None, **kwargs):
        super().__init__(instance, data, **kwargs)
        if fields:
            self.Meta.fields = fields

    def to_representation(self, instance):
        """
        Convert all dictionary keys to uppercase for frontend readability.
        """
        ret = super().to_representation(instance)
        result = {k.upper(): v for k, v in ret.items()}

        return result

    def is_valid(self, *, raise_exception=False):
        """
        Customise the is_valid method to return a custom error message.
        """
        try:
            return super().is_valid(raise_exception=raise_exception)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError(
                {"error": exc.detail}, code=exc.status_code
            )


class PaginationSerializer(PageNumberPagination):
    """
    This serializer is used to paginate the data in the response
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def __init__(self, **kwargs):
        super().__init__()
        self.page_query_param = "page"
        self.request = kwargs.get("request", None)

    def paginate_queryset(self, queryset, request, view=None):
        try:
            page_size = self.get_page_size(request)
            if not page_size:
                return None

            paginator = self.django_paginator_class(queryset, page_size)
            page_number = request.query_params.get(self.page_query_param, 1)
            if not page_number.isdigit() or int(page_number) < 1:
                page_number = 1

            if page_number in self.last_page_strings:
                page_number = paginator.num_pages

            try:
                page = paginator.page(page_number)
            except InvalidPage as exc:
                raise NotFound(f"Invalid page ({page_number}): {str(exc)}") from exc

            # pylint: disable=W0201
            self.page = page

            return list(page)
        except Exception as exc:
            raise APIException(str(exc)) from exc

    def get_next_page_number(self):
        try:
            if not self.page:
                return None
            if not self.page.has_next():
                return None
            return self.page.next_page_number()
        except ValueError:
            return None

    def get_paginated_response(self, data):
        try:
            return Response(
                {
                    "data": data,
                    "metadata": {
                        "page": self.page.number,
                        "page_size": self.page.paginator.per_page,
                        "total": self.page.paginator.count,
                        "next_page": self.get_next_page_number(),
                        "previous_page": (
                            self.page.previous_page_number()
                            if self.page.has_previous()
                            else None
                        ),
                    },
                }
            )
        except APIException as exc:
            return Response({"error": str(exc)}, status=500)
