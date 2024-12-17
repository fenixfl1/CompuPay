# pylint: disable=broad-except

import base64
from io import BytesIO
import os
from datetime import datetime
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from users.models import Business


def template(
    buffer: BytesIO,
    title: str,
    user: str = "Usuario",
    orientation: str = "portrait",
) -> tuple[canvas.Canvas, BytesIO, float, float]:
    """
    Crea una plantilla base para reportes en PDF.

    :param buffer: Objeto BytesIO para almacenar el PDF.
    :param title: Título del reporte.
    :param user: Nombre del usuario que genera el reporte.
    :param orientation: Orientación del reporte ("portrait" o "landscape").
    :return: Una tupla con el canvas del PDF, el buffer, el ancho y la posición Y inicial.
    """
    # Configurar orientación y tamaño de la página
    page_size = A4 if orientation == "portrait" else landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=page_size)
    width, height = page_size

    business = Business.objects.first()

    # Verificación del logo en base64
    logo_base64 = business.logo
    if logo_base64.startswith("data:image"):
        logo_base64 = logo_base64.split(",")[1]  # Eliminar el prefijo 'data:image'

    try:
        logo_data = base64.b64decode(logo_base64)
    except Exception as e:
        print(f"Error al decodificar el logo: {e}")
        logo_data = b""  # En caso de error, no se carga el logo

    if logo_data:
        logo_stream = BytesIO(logo_data)

        # Usar Pillow para abrir y procesar la imagen
        image = Image.open(logo_stream)
        image = image.convert("RGB")

        processed_logo_stream = BytesIO()
        image.save(processed_logo_stream, format="PNG")
        processed_logo_stream.seek(0)

        # Crear el objeto ImageReader de ReportLab
        logo_image = ImageReader(processed_logo_stream)

        # Dibujar la imagen en el PDF, ajustando la posición si es necesario
        pdf.drawImage(logo_image, 50, height - 70, width=50, height=50)

    # Alineación de texto en la primera línea (logo + título + fecha + usuario)
    y_header = height - 50
    pdf.setFont("Helvetica-Bold", 16)

    # Alinear nombre de la empresa a la izquierda
    pdf.drawString(110, y_header, business.name)

    # Alinear título a la izquierda
    pdf.setFont("Helvetica", 12)
    pdf.drawString(110, y_header - 20, title)

    # Alinear fecha y usuario a la derecha en la misma línea
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        width - 250, y_header - 20, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}"
    )
    pdf.drawString(width - 250, y_header - 40, f"Generado por: {user}")

    # Línea divisoria
    pdf.setStrokeColor(colors.gray)
    pdf.line(50, y_header - 50, width - 50, y_header - 50)

    # Pie de página
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 30, f"© {business.name} - Todos los derechos reservados")
    pdf.drawString(width - 100, 30, f"Página {pdf.getPageNumber()}")

    # Retornar el canvas, buffer y posición inicial para el contenido
    initial_y_position = y_header - 150  # Ajusta este valor según necesites
    return pdf, buffer, width, initial_y_position


def draw_table(
    data,
    column_widths=None,
    alternate_row_colors=("#ffffff", "#e6fffb"),
    header_background="#73d13d",
    header_text_color=None,
    alignment="LEFT",
):
    """
    Genera una tabla estilizada a partir de una lista de diccionarios.

    :param data: Lista de diccionarios con los datos a mostrar.
    :param column_widths: Anchos de las columnas (lista de números o None para cálculo automático).
    :param alternate_row_colors: Tuple con colores para alternar filas (fondo claro y oscuro).
    :param header_background: Color de fondo de los encabezados.
    :param header_text_color: Color del texto de los encabezados.
    :param alignment: Alineación del contenido de las columnas ("LEFT", "CENTER", "RIGHT").
    :return: Una instancia de Table estilizada.
    """
    if not data:
        raise ValueError("No hay datos para crear la tabla.")

    # Generar encabezados desde las claves del primer registro
    headers = list(data[0].keys())

    # Generar las filas (incluye encabezados)
    rows = [headers] + [[row.get(header, "") for header in headers] for row in data]

    # Ajustar anchos de columna si no se proporcionaron
    if not column_widths:
        column_widths = [80] * len(headers)

    # Crear la tabla
    table = Table(rows, colWidths=column_widths)

    # Estilos básicos
    style = TableStyle(
        [
            ("ALIGN", (0, 0), (-1, -1), alignment),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TEXTCOLOR", (0, 0), (-1, 0), header_text_color or colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), header_background or colors.grey),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]
    )

    # Alternar colores en filas
    if alternate_row_colors:
        for i, _ in enumerate(rows[1:], start=1):
            bg_color = alternate_row_colors[i % 2]  # Alternar colores
            style.add("BACKGROUND", (0, i), (-1, i), bg_color)

    table.setStyle(style)
    return table
