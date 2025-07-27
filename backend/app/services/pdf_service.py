from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO
from typing import List, Dict

def split_text(text: str, max_chars: int = 90) -> List[str]:
    words = text.split()
    lines = []
    line = ""
    for word in words:
        if len(line + word) <= max_chars:
            line += word + " "
        else:
            lines.append(line.strip())
            line = word + " "
    if line:
        lines.append(line.strip())
    return lines

def generate_pdf_bytes(metadata: Dict[str, str], messages: List[Dict[str, str]]) -> BytesIO:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Date: {metadata['date']}")
    y -= 20
    c.drawString(50, y, f"Username: {metadata['username']}")
    y -= 20
    c.drawString(50, y, f"Bot Name: {metadata['bot_name']}")
    y -= 40

    c.setFont("Helvetica", 11)
    for msg in messages:
        text = f"{msg['sender'].value.capitalize()}: {msg['text']}"
        for line in split_text(text):
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 11)
            c.drawString(50, y, line)
            y -= 15

    c.save()
    buffer.seek(0)
    return buffer

def get_pdf_conversation(metadata: Dict[str, str], messages: List[Dict[str, str]]) -> BytesIO:
    return generate_pdf_bytes(metadata, messages)
