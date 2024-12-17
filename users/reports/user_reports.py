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
    data: list[User],
    title: str,
    user: str,
    column_widths: list[int],
    is_landscape: bool = False,
) -> str:
    buffer = BytesIO()
    pdf, buffer, width, y_position = template(
        buffer=buffer,
        user=user,
        title=title,
        orientation="landscape" if is_landscape else "portrait",
    )

    table = draw_table(
        data=data,
        column_widths=column_widths,
    )

    table.wrapOn(pdf, width, y_position)
    table.drawOn(pdf, 50, y_position - len(data) * 15)

    pdf.save()
    pdf_data = buffer.getvalue()
    buffer.close()

    encoded_pdf = base64.b64encode(pdf_data).decode("utf-8")

    return encoded_pdf
