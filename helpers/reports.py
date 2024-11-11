from io import BytesIO
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas


business_name = os.getenv("BUSINESS_NAME", "Nombre Empresa")


def template(
    buffer: BytesIO, title: str, orientation: str = "portrait"
) -> tuple[Canvas, BytesIO, float, float]:
    pdf = Canvas(buffer, pagesize=A4 if orientation == "portrait" else landscape(A4))
    width, height = A4 if orientation == "portrait" else landscape(A4)

    # Dibujar encabezado
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, height - 50, business_name)

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, height - 70, title)
    pdf.drawString(50, height - 90, f"Fecha {datetime.now().strftime('%d/%m/%Y')}")

    pdf.setStrokeColor(colors.gray)
    pdf.line(50, height - 100, width - 50, height - 100)

    # Pie de página
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 30, f"© {business_name} - Todos los derechos reservados")
    pdf.drawString(width - 100, 30, f"Página {pdf.getPageNumber()}")

    # Nueva posición Y para empezar la tabla debajo del título
    initial_y_position = height - 150  # Ajusta este valor según necesites

    return pdf, buffer, width, initial_y_position


def draw_table(pdf, data, fields, y_position, column_widths, _width=A4[0]):
    """
    Función genérica para dibujar una tabla en un reporte PDF con anchos de columna personalizados.

    :param pdf: Objeto de tipo Canvas de ReportLab.
    :param data: Lista de instancias del modelo con los datos a mostrar.
    :param fields: Lista de diccionarios con los nombres de los campos y las etiquetas.
    :param y_position: Posición Y en la que se empieza a dibujar la tabla.
    :param column_widths: Lista o tupla con los anchos de cada columna.
    :param _width: Ancho de la página, por defecto es el ancho de A4.
    :return: La nueva posición Y después de dibujar la tabla.
    """
    margin_left = 50

    # Validar que la longitud de column_widths coincida con el número de campos
    if len(column_widths) != len(fields):
        raise ValueError(
            "La longitud de 'column_widths' debe coincidir con el número de campos en 'fields'."
        )

    # Dibujar el encabezado
    pdf.setFont("Helvetica-Bold", 10)
    x_position = margin_left
    for i, field in enumerate(fields):
        pdf.drawString(x_position, y_position, field["label"])
        x_position += column_widths[i]  # Sumar el ancho de cada columna

    y_position -= 20

    # Dibujar filas
    pdf.setFont("Helvetica", 10)
    for row in data:
        # Comprobar si es necesario una nueva página
        if y_position < 50:
            pdf.showPage()

            # Dibujar el encabezado en la nueva página
            pdf.setFont("Helvetica-Bold", 10)
            y_position = A4[1] - 50
            x_position = margin_left
            for i, field in enumerate(fields):
                pdf.drawString(x_position, y_position, field["label"])
                x_position += column_widths[i]
            y_position -= 20

        # Dibujar los valores de la fila
        x_position = margin_left
        for i, field in enumerate(fields):
            value = getattr(row, field["field"], "")
            pdf.drawString(x_position, y_position, str(value or ""))
            x_position += column_widths[i]

        # Dibujar una línea de separación después de la fila
        pdf.line(margin_left, y_position - 2, _width - margin_left, y_position - 2)

        y_position -= 15

    return y_position
