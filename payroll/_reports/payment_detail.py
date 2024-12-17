import base64
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from helpers.reports import draw_table, template


def payroll_report(data, title, user, is_landscape=False):
    """
    Genera un reporte PDF de nómina con encabezado y tabla.

    :param data: Lista de objetos o diccionarios con los datos de la nómina.
    :param title: Título del reporte.
    :param user: Nombre del usuario que genera el reporte.
    :param is_landscape: Si el reporte debe generarse en orientación horizontal.
    :return: PDF codificado en base64.
    """
    # Validar que existan datos
