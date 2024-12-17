import base64
from io import BytesIO
from reportlab.pdfgen import canvas

from helpers.reports import draw_table, template


class PayrollRepostService:
    def __init__(self, user: str, is_landscape: bool = False):
        self.user = user
        self.is_landscape = is_landscape

    def __template(
        self, buffer: BytesIO, title: str
    ) -> tuple[canvas.Canvas, BytesIO, float, float]:
        return template(
            buffer=buffer,
            title=title,
            user=self.user,
            orientation="landscape" if self.is_landscape else "portrait",
        )

    def payroll(self, data: dict, title: str) -> str:
        """Generate payroll report

        Args:
            data (dict): The data to draw in the document
            title (str): The report title

        Returns:
            str: pdf in base64 string format
        """
        buffer = BytesIO()
        pdf, buffer, width, initial_y_position = self.__template(buffer, title)

        table = draw_table(
            data, column_widths=[40, 120, 80, 60, 80, 60, 60, 60, 60, 60]
        )

        table.wrapOn(pdf, width, initial_y_position)
        table.drawOn(pdf, 50, initial_y_position - (len(data) * 15))

        pdf.save()
        pdf_data = buffer.getvalue()
        buffer.close()

        encoded_pdf = base64.b64encode(pdf_data).decode("utf-8")
        return encoded_pdf

    def payment_details(self, data: dict, title: str) -> str:
        """This method generate a payment details report

        Args:
            data (dict): The data to draw in the report
            title (str): The report title

        Returns:
            str: pdf in base64 string format
        """
        buffer = BytesIO()
        pdf, buffer, width, initial_y_position = self.__template(buffer, title)

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
