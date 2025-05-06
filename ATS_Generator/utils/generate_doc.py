from fpdf import FPDF
import os

def create_pdf(text, original_name):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for line in text.split('\n'):
        pdf.multi_cell(0, 10, line.strip())

    os.makedirs("optimized", exist_ok=True)
    filename = f"optimized/optimized_{original_name.replace(' ', '_')}.pdf"
    pdf.output(filename)
    return filename
