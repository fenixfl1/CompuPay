import base64
from io import BytesIO
import re
from django.db.models import QuerySet
from django.core.files.storage import default_storage
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4

from helpers.reports import template, draw_table
from helpers.translations import USER_COLUMN_TRANSLATIONS
from users.models import User, ActivityLog


def generate_user_report(
    query: QuerySet[User], title: str, fields: list[str], column_widths: list[int]
) -> str:
    buffer = BytesIO()
    pdf, buffer, page_width, y_position = template(buffer, title, "landscape")

    report_fields = [
        {"label": USER_COLUMN_TRANSLATIONS.get(field, field), "field": field}
        for field in fields
    ]

    y_position = draw_table(
        pdf, query, report_fields, y_position, column_widths, page_width
    )

    pdf.save()

    filename = re.sub(r"\s+", "_", title)
    file_path = f"users/reports/{filename.lower()}.pdf"
    with default_storage.open(file_path, "wb") as f:
        f.write(buffer.getvalue())

    buffer.seek(0)
    base64_pdf = base64.b64encode(buffer.getvalue()).decode("utf-8")
    buffer.close()

    return base64_pdf
