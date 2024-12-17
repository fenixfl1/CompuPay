import base64
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen.canvas import Canvas

from helpers.reports import draw_table, template


def generate_payroll_report(data, title, user, is_landscape=False):
    """
    Genera un reporte PDF de nómina con encabezado y tabla.

    :param payments: Lista de objetos o diccionarios con los datos de la nómina.
    :param title: Título del reporte.
    :param user: Nombre del usuario que genera el reporte.
    :param columns: Lista de anchos de columnas.
    :param fields: Lista de diccionarios con los campos y etiquetas de la tabla.
    :param is_landscape: Si el reporte debe generarse en orientación horizontal.
    :return: PDF codificado en base64.
    """
    buffer = BytesIO()

    pdf, buffer, width, initial_y_position = template(
        buffer=buffer,
        title=title,
        user=user,
        orientation="landscape" if is_landscape else "portrait",
    )

    table = draw_table(data, column_widths=[40, 120, 80, 60, 80, 60, 60, 60, 60, 60])

    table.wrapOn(pdf, width, initial_y_position)
    table.drawOn(pdf, 50, initial_y_position - (len(data) * 15))

    pdf.save()
    pdf_data = buffer.getvalue()
    buffer.close()

    # Codificar en Base64 para transmitir el archivo
    encoded_pdf = base64.b64encode(pdf_data).decode("utf-8")
    return encoded_pdf


def payroll_entries_payment(
    data: dict, title: str, user: str, is_landscape: bool = False
) -> str:
    buffer = BytesIO()

    pdf, buffer, width, initial_y_position = template(
        buffer,
        title=title,
        user=user,
        orientation="landscape" if is_landscape else "portrait",
    )

    table = draw_table(
        data=data,
        alignment="CENTER",
    )

    available_height = initial_y_position - 50
    table_height = len(data) * 20  # Estimar el espacio necesario para la tabla
    start_y = max(available_height - table_height, 50)

    table.wrapOn(pdf, width, available_height)
    table.drawOn(pdf, 50, start_y)

    pdf.save()
    pdf_data = buffer.getvalue()
    buffer.close()

    encoded_pdf = base64.b64encode(pdf_data).decode("utf-8")
    return encoded_pdf
