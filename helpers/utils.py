from datetime import datetime
from django.db.models import Q
from django.forms import ValidationError
from rest_framework.exceptions import APIException

from helpers.constants import (
    INVALID_DATE_FORMAT,
    INVALID_LIST_VALUE,
    MSG_INVALID_ISO_DATE,
    MSG_INVALID_OPERATOR_FOR_LIST,
    MSG_INVALID_VALUE,
)
from helpers.exceptions import get_traceback


def ordinal(number, language="es"):
    def ordinal_en(n):
        suffix = ["th", "st", "nd", "rd"] + ["th"] * 6
        if 10 <= n % 100 <= 20:
            suffix_index = 0
        else:
            suffix_index = min(n % 10, 4)
        return f"{n}{suffix[suffix_index]}"

    def ordinal_es(n):
        if n == 1:
            return f"{n}ra"
        elif n == 3:
            return f"{n}ra"
        elif n == 2:
            return f"{n}da"
        elif n == 4:
            return f"{n}ta"
        elif n == 5:
            return f"{n}ta"
        else:
            return f"{n}º"

    if language == "en":
        return ordinal_en(number)
    elif language == "es":
        return ordinal_es(number)
    else:
        raise ValueError(
            "Unsupported language. Use 'en' for English or 'es' for Spanish."
        )


def list_values_to_lower(values: list | None) -> list | None:
    if isinstance(values, list):
        return [value.lower() for value in values]
    return None


def dict_key_to_lower(data: dict | list[dict]) -> dict | list[dict]:
    """
    This function is used to convert the key of the dictionary to lower case
    """
    try:
        if not isinstance(data, (dict, list)):
            raise APIException(
                f"Invalid data type. Expected 'dict' or 'list[dict]' but got '{type(data)}'"
            )
        if isinstance(data, dict):
            return {k.lower(): v for k, v in data.items()}
        elif isinstance(data, list):
            return [{k.lower(): v for k, v in item.items()} for item in data]
    except Exception as e:
        raise APIException(f"{e}. Raised in 'dict_key_to_lower()' function", 500) from e


def advanced_query_filter(conditions: list[dict]) -> tuple[Q, list[dict]]:
    """
    This function is used to build the query filter based on
    the conditions received in the request.\n
    The supported operators are:
    * `LIKE` (case-insensitive)
    * `ILIKE` (case-insensitive)
    * `=` (default)
    * `!=` (not equal)
    * `<`  (less than)
    * `<=` (less than or equal)
    * `>` (greater than)
    * `>=`  (greater than or equal)
    * `IN` (in list)
    * `NOT IN` (not in list)
    * `IS NULL` (is null)
    * `BETWEEN` (between two values)\n`
    """
    query = Q()
    exclude_conditions = []
    lookup = ""
    for condition in conditions:
        field: str | list = condition.get("field")
        operator: str = condition.get("operator", "").upper()
        value: str | int | bool = condition.get("condition")
        data_type: str = condition.get("dataType")

        if not field or not operator or not condition:
            raise APIException(
                "Invalid condition format. Each condition must include 'field', 'operator', and 'condition' keys."
            )

        operator_map = {
            "=": "",
            "!=": "__ne",
            "LIKE": "__icontains",
            "ILIKE": "__icontains",
            ">": "__gt",
            ">=": "__gte",
            "<": "__lt",
            "<=": "__lte",
            "IN": "__in",
            "IS NULL": "__isnull",
            "BETWEEN": "__range",
        }

        data_type_map = {
            "date": "date",
            "int": "int",
            "str": "str",
            "bool": "bool",
            "list": "list",
        }

        if operator not in operator_map:
            raise APIException(
                f"Invalid operator: {operator}. Supported operators are: {operator_map.keys()}"
            )
        if data_type not in data_type_map:
            raise APIException(
                f"Invalid data type: {data_type}. Supported data types are: {data_type_map.keys()}"
            )

        if operator == "IS NULL" and data_type != "bool":
            raise APIException(
                f"Invalid condition for operator 'IS NULL'. Expected a boolean value but got '{data_type}'"
            )

        if operator in ["IN", "NOT IN", "BETWEEN"] and not isinstance(value, list):
            raise APIException(
                f"Invalid value for operator '{operator}'. Expected a list but got '{type(value)}'"
            )

        match data_type:
            case "data":
                try:
                    value = datetime.fromisoformat(value).date()
                except ValueError as exc:
                    get_traceback()
                    raise APIException(
                        detail=MSG_INVALID_ISO_DATE % field, code=INVALID_DATE_FORMAT
                    ) from exc
            case "int":
                try:
                    value = int(value)
                except ValueError as exc:
                    raise APIException(
                        f"Invalid integer format for field {field}"
                    ) from exc
            case "bool":
                try:
                    if not isinstance(value, bool):
                        raise ValueError(f"Invalid boolean format for field '{field}'")
                    value = bool(value)
                except Exception as exc:
                    raise APIException(
                        f"Invalid boolean format for field {field}"
                    ) from exc
            case "list":
                try:
                    if not isinstance(value, list):
                        raise ValueError(
                            MSG_INVALID_VALUE % {"data_type": "list", "field": field}
                        )
                    if operator not in ["IN", "NOT IN", "BETWEEN"]:
                        raise ValueError(MSG_INVALID_OPERATOR_FOR_LIST % operator)
                except ValueError as exc:
                    raise APIException(
                        detail=str(exc), code=INVALID_LIST_VALUE
                    ) from exc

        if isinstance(field, list):
            sub_query = Q()
            for f in field:
                lookup = f"{f.lower()}{operator_map[operator]}"
                sub_query |= Q(**{lookup: value})
            query &= sub_query
        else:
            lookup = f"{field.lower()}{operator_map[operator]}"

            if operator == "!=":
                exclude_conditions.append({field.lower(): value})
            else:
                query &= Q(**{lookup: value})

    return query, exclude_conditions


def simple_query_filter(conditon: dict) -> Q:
    """
    This function is used to build the query filter based on the condition received in the request.\n
    The format of the condition is:
    {
        user_id: 1,
        username: "admin",
        ...[any_field]: [any_value]
    }
    this function works over any model and any field.
    """
    # build a condition like:
    # Q(user_id=1, username="admin", ...[any_field]=[any_value])
    return Q(**dict_key_to_lower(conditon))


def get_month_day_name(int_value: int, opt: str) -> str:
    """Returns the name of the month or day based on the given integer value.

    Args:
        int_value (int): The number of the month or day (e.g., 1 -> Monday or January).
        opt (str): 'day' or 'month' to specify the type of name to return.

    Returns:
        str: The name of the month or day.
    """
    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    months = [
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    ]

    if opt.lower() == "day":
        if 1 <= int_value <= 7:
            return days[int_value - 1]
        else:
            return "Invalid day number"
    elif opt.lower() == "month":
        if 1 <= int_value <= 12:
            return months[int_value - 1]
        else:
            return "Invalid month number"
    else:
        return "Invalid option"


def inrange(n, range1, range2) -> bool:
    return range1[0] <= n <= range1[1] or range2[0] <= n <= range2[1]
