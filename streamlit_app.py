
import io
import zipfile
import smtplib
import re
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

import streamlit as st

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Circle, Rect, Line, Polygon
from PIL import Image as PILImage, ImageOps


# =========================================================
# PROPUESTA MKT — Características del diseño en un solo campo abierto
# Config + Branding (mismo estilo que Solicitud de Producción)
# =========================================================
PRIMARY = "#252525"
PRIMARY_DARK = "#0F0F0F"
ACCENT_BG = "#F2F2F2"
GREY_LIGHT = "#F7F7F7"
GREY_BORDER = "#D2D2D2"
TEXT_DARK = "#1A1A1A"

st.set_page_config(
    page_title="Brief de Diseño · Edición Personalizada · Círculo Tequila",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
    <style>
    .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; }}
    [data-baseweb="select"] span {{ font-size: 0.9rem; }}
    .stButton > button[kind="primary"] {{
        background-color: {PRIMARY}; border-color: {PRIMARY}; color: white;
        font-weight: 600;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {PRIMARY_DARK}; border-color: {PRIMARY_DARK};
    }}
    .brand-bar {{
        background: linear-gradient(90deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        color: white; padding: 14px 22px; border-radius: 10px;
        font-weight: 700; font-size: 1.35rem; letter-spacing: 0.4px;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.18);
        display: flex; align-items: center; justify-content: space-between;
    }}
    .brand-bar small {{ font-weight: 400; opacity: 0.9; font-size: 0.78rem; }}
    .section-header {{
        border-left: 4px solid {PRIMARY};
        padding: 4px 0 4px 12px;
        margin: 1.2rem 0 0.4rem 0;
    }}
    .section-header h3 {{
        margin: 0; color: {TEXT_DARK}; font-size: 1.05rem; font-weight: 700;
    }}
    .section-header span.sub {{
        color: #555; font-size: 0.82rem; font-weight: 400;
    }}
    .progress-item {{
        display: flex; align-items: center; gap: 8px;
        padding: 6px 8px; border-radius: 6px; margin: 2px 0;
        font-size: 0.86rem;
    }}
    .progress-item.done {{ background: #E8F5E9; color: #1B5E20; }}
    .progress-item.todo {{ background: #FAFAFA; color: #777; }}
    .intro-card {{
        background: {ACCENT_BG}; border: 1px solid {GREY_BORDER};
        border-radius: 10px; padding: 16px 18px; margin-bottom: 1rem;
        font-size: 0.92rem; color: {TEXT_DARK};
    }}
    div[data-testid="stExpander"] {{
        border: 1px solid {GREY_BORDER} !important;
        border-radius: 8px !important;
    }}

    /* Título del expander de ejemplos */
    div[data-testid="stExpander"] summary p {{
        font-size: 1.08rem !important;
        font-weight: 700 !important;
        color: {TEXT_DARK} !important;
    }}

    .stAlert {{ border-radius: 8px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

MESES_ES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO",
    7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}


TAMANO_MAX_ADJUNTOS_MB = 15
TAMANO_MAX_ZIP_CORREO_MB = 18

TIPOS_ADJUNTOS_PERMITIDOS = [
    "png",
    "jpg",
    "jpeg",
    "webp",
    "pdf",
    "svg",
    "ai",
    "eps",
]

ASESORES = {
    "Mercedes Baltazar": "mbaltazar@circulotequila.com",
    "Jorge Ocampo": "turismo@circulotequila.com",
    "Nancy Madariaga": "nancymadariaga@circulotequila.com",
    "Cinthya Sandoval": "ventas@circulotequila.com",
    "Arturo García": "algarcia@circulotequila.com",
    "Gustavo Aguiar": "gaguiar@circulotequila.com",
    "Fabiola Chacón": "fabychacon.circulotequila@gmail.com",
    "Silvia Almaraz": "empresarial.cdmx@circulotequila.com",
    "Marielle Estrada": "recursoshumanos@circulotequila.com",
    "Kenia Torres": "mktdigital@circulotequila.com",
    "Ricardo Salcedo": "rsalcedo@circulotequila.com",
    "Israel Chavira": "ichavira@circulotequila.com",
    "Antonio Rodríguez": "operaciones@circulotequila.com",
}

ASESOR_OTRO = "Otro / No aparece en la lista"


# =========================================================
# Helpers
# =========================================================
def fecha_es(dt: datetime) -> str:
    return f"{dt.day:02d}/{MESES_ES[dt.month]}/{dt.year}"


def get_solapa_path() -> Path | None:
    base = Path(__file__).resolve().parent
    candidates = [
        base / "assets" / "solapa.jpg",
        base / "assets" / "solapa.jpeg",
        base / "assets" / "solapa.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# Galería de "inspiración": ejemplos de botellas ya diseñadas, solo para que
# el cliente se dé una idea de lo que puede lograr al llenar el brief. Cada
# imagen vive en assets/ejemplos/ junto al .py; si el archivo no existe (por
# ejemplo, aún no lo subiste a tu repo), simplemente se omite sin romper la
# app.

SPIN_EJEMPLOS = [
    {
        "titulo": "Luna Llena",
        "url": "https://mariana01.sirv.com/Luna%20Llena/Luna%20Llena.spin?initializeOn=click",
        "desc": "Edición artística · vista 360°",
    },
    {
        "titulo": "Theralis",
        "url": "https://mariana01.sirv.com/Theralist/Theralist.spin?initializeOn=click",
        "desc": "Edición empresarial · vista 360°",
    },
    {
        "titulo": "Alfran",
        "url": "https://mariana01.sirv.com/Alfran/Alfran.spin?initializeOn=click",
        "desc": "Edición empresarial · vista 360°",
    },
    {
        "titulo": "Milwaukee",
        "url": "https://mariana01.sirv.com/Milwaukee/Milwaukee.spin?initializeOn=click",
        "desc": "Edición conmemorativa · vista 360°",
    },
    {
        "titulo": "Construcción",
        "url": "https://mariana01.sirv.com/Deconstrucci%C3%B3n/Deconstrucci%C3%B3n.spin?initializeOn=click",
        "desc": "Edición institucional · vista 360°",
    },
    {
        "titulo": "Boda M&R",
        "url": "https://mariana01.sirv.com/M%26R/M%26R.spin?initializeOn=click",
        "desc": "Edición personalizada · vista 360°",
    },
    {
        "titulo": "Nadadora",
        "url": "https://mariana01.sirv.com/Turismo%2002/Turismo%2002.spin?initializeOn=click",
        "desc": "Vista 360°",
    },
    {
        "titulo": "Wedding Week",
        "url": "https://mariana01.sirv.com/Wedding%20Week/Otra%20wedding%20week/Otra%20wedding%20week.spin?initializeOn=click",
        "desc": "Vista 360°",
    },
    {
        "titulo": "Unión",
        "url": "https://mariana01.sirv.com/Uni%C3%B3n/Uni%C3%B3n.spin?initializeOn=click",
        "desc": "Vista 360°",
    },
]
def section_header(title: str, sub: str = ""):
    sub_html = f'<span class="sub"> · {sub}</span>' if sub else ""
    st.markdown(
        f'<div class="section-header"><h3>{title}{sub_html}</h3></div>',
        unsafe_allow_html=True,
    )


def es_imagen(nombre: str) -> bool:
    ext = Path(nombre).suffix.lower()
    return ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")


def es_correo_valido(correo: str) -> bool:
    correo = correo.strip()
    if "@" not in correo or "." not in correo.split("@")[-1]:
        return False
    return True


def tam_legible(num_bytes: int) -> str:
    for unidad in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unidad}" if unidad == "B" else f"{num_bytes:.1f} {unidad}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def ahora_mexico() -> datetime:
    return datetime.now(ZoneInfo("America/Mexico_City"))


def texto_pdf_seguro(valor) -> str:
    """Escapa texto ingresado por el usuario antes de enviarlo a ReportLab."""
    if valor is None or valor == "":
        return "—"
    return escape(str(valor))


def texto_canvas_seguro(valor) -> str:
    """Convierte texto a caracteres compatibles con las fuentes base de ReportLab."""
    texto = str(valor or "")
    return texto.encode("cp1252", errors="replace").decode("cp1252")


def nombre_archivo_seguro(valor: str, predeterminado: str = "archivo") -> str:
    """Genera nombres seguros para archivos y rutas internas del ZIP."""
    nombre = Path(str(valor or "")).name.strip()
    nombre = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ._-]+", "_", nombre)
    nombre = nombre.strip("._-")
    return nombre or predeterminado


def preparar_imagen_para_pdf(contenido: bytes) -> bytes:
    """Crea una vista previa ligera para el PDF sin alterar el archivo original del ZIP."""
    with PILImage.open(io.BytesIO(contenido)) as imagen:
        imagen = ImageOps.exif_transpose(imagen)

        if getattr(imagen, "is_animated", False):
            imagen.seek(0)

        if imagen.mode in ("RGBA", "LA"):
            fondo = PILImage.new("RGB", imagen.size, "white")
            canal_alpha = imagen.getchannel("A")
            fondo.paste(imagen.convert("RGB"), mask=canal_alpha)
            imagen = fondo
        elif imagen.mode != "RGB":
            imagen = imagen.convert("RGB")

        imagen.thumbnail((1600, 1200))
        salida = io.BytesIO()
        imagen.save(salida, format="JPEG", quality=78, optimize=True)
        return salida.getvalue()


# =========================================================
# Session State init
# =========================================================
if "form_gen" not in st.session_state:
    st.session_state.form_gen = 0

if "submitted" not in st.session_state:
    st.session_state.submitted = False

if "submit_result" not in st.session_state:
    st.session_state.submit_result = {}


def reiniciar_formulario():
    st.session_state.form_gen += 1
    st.session_state.submitted = False
    st.session_state.submit_result = {}


# =========================================================
# Header / Solapa
# =========================================================
solapa_path = get_solapa_path()
if solapa_path:
    # Solapa centrada al 75% aprox. del ancho disponible.
    # Las columnas laterales funcionan como márgenes visuales.
    col_solapa_izq, col_solapa_centro, col_solapa_der = st.columns([1, 6, 1])
    with col_solapa_centro:
        st.image(str(solapa_path), use_container_width=True)

st.markdown(
    """
    <div class="brand-bar">
        <span>BRIEF DE DISEÑO · EDICIÓN PERSONALIZADA</span>
        <small>Círculo Tequila · Marketing</small>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Generación de PDF (mismo estilo visual que Solicitud de Producción)
# =========================================================
PDF_RED = colors.HexColor(PRIMARY)
PDF_RED_DARK = colors.HexColor(PRIMARY_DARK)
PDF_LIGHT_BG = colors.HexColor(ACCENT_BG)
PDF_GREY_ROW = colors.HexColor("#F7F7F7")
PDF_GREY_BORDER = colors.HexColor("#D9D9D9")
PDF_TEXT = colors.HexColor("#1A1A1A")
PDF_MUTED = colors.HexColor("#666666")


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, proyecto="", empresa="", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.proyecto = proyecto
        self.empresa = empresa

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(total_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_footer(self, total_pages):
        page_num = self._pageNumber
        width, _height = A4
        self.setStrokeColor(PDF_RED)
        self.setLineWidth(1.2)
        self.line(1.3 * cm, 1.35 * cm, width - 1.3 * cm, 1.35 * cm)
        self.setStrokeColor(PDF_GREY_BORDER)
        self.setLineWidth(0.4)
        self.line(1.3 * cm, 1.20 * cm, width - 1.3 * cm, 1.20 * cm)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(PDF_TEXT)
        empresa = texto_canvas_seguro(self.empresa or "No especificada")
        proyecto = texto_canvas_seguro(self.proyecto)
        emp_txt = empresa if len(empresa) <= 36 else empresa[:33] + "..."
        proy_txt = proyecto if len(proyecto) <= 36 else proyecto[:33] + "..."
        footer_y = 0.75 * cm
        self.drawString(1.3 * cm, footer_y, f"Empresa: {emp_txt}")
        self.drawCentredString(width / 2, footer_y, f"Proyecto: {proy_txt}")
        self.drawRightString(width - 1.3 * cm, footer_y, f"Pág. {page_num} / {total_pages}")
        self.setFont("Helvetica-Oblique", 7)
        self.setFillColor(PDF_MUTED)
        self.drawCentredString(width / 2, 0.40 * cm,
            "Círculo Tequila · Marketing — Brief de Diseño (Edición Personalizada)")


def _P(txt, style):
    return Paragraph(texto_pdf_seguro(txt), style)


def build_brief_pdf(datos: dict, adjuntos_por_seccion: dict) -> bytes:
    """
    Genera un PDF compacto y visual:
    - solapa corporativa reducida y centrada;
    - secciones con iconografía vectorial compatible con ReportLab;
    - características del diseño en bloques amigables;
    - material de referencia en miniaturas de dos columnas.
    """
    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    title_style = ParagraphStyle(
        "title_style",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=0,
        leading=19,
    )
    subtitle_style = ParagraphStyle(
        "subtitle_style",
        parent=normal,
        fontName="Helvetica",
        fontSize=8.5,
        textColor=colors.white,
        alignment=TA_CENTER,
        leading=10,
    )
    sec_style = ParagraphStyle(
        "sec_style",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        textColor=colors.white,
        spaceBefore=0,
        spaceAfter=0,
        leading=13,
        alignment=TA_LEFT,
    )
    label_style = ParagraphStyle(
        "label_style",
        parent=normal,
        fontName="Helvetica",
        fontSize=8.6,
        textColor=PDF_TEXT,
        leading=11,
    )
    value_style = ParagraphStyle(
        "value_style",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=9.1,
        textColor=PDF_RED_DARK,
        leading=11,
    )
    body_style = ParagraphStyle(
        "body_style",
        parent=normal,
        fontName="Helvetica",
        fontSize=9,
        textColor=PDF_TEXT,
        leading=12.2,
    )
    small_style = ParagraphStyle(
        "small_style",
        parent=normal,
        fontName="Helvetica",
        fontSize=7.6,
        textColor=PDF_MUTED,
        leading=9,
        alignment=TA_CENTER,
    )
    file_list_style = ParagraphStyle(
        "file_list_style",
        parent=normal,
        fontName="Helvetica",
        fontSize=8.2,
        textColor=PDF_TEXT,
        leading=11,
    )

    def L(txt):
        return Paragraph(str(txt), label_style)

    def V(txt):
        return Paragraph(
            f"<b>{texto_pdf_seguro(txt)}</b>",
            value_style,
        )

    def icono_pdf(tipo: str, color="#FFFFFF", size=17):
        """Pequeños pictogramas vectoriales; no dependen de emojis ni fuentes externas."""
        c = colors.HexColor(color)
        d = Drawing(size, size)
        s = size / 18.0

        def X(v):
            return v * s

        if tipo == "idea":
            d.add(Circle(X(9), X(10.5), X(4.4), strokeColor=c, fillColor=None, strokeWidth=X(1.5)))
            d.add(Line(X(7), X(5.3), X(11), X(5.3), strokeColor=c, strokeWidth=X(1.5)))
            d.add(Line(X(7.5), X(3.5), X(10.5), X(3.5), strokeColor=c, strokeWidth=X(1.5)))
            d.add(Line(X(9), X(15.8), X(9), X(18), strokeColor=c, strokeWidth=X(1.2)))
        elif tipo == "personas":
            d.add(Circle(X(6), X(12.2), X(2.3), strokeColor=c, fillColor=None, strokeWidth=X(1.4)))
            d.add(Circle(X(12), X(12.2), X(2.3), strokeColor=c, fillColor=None, strokeWidth=X(1.4)))
            d.add(Line(X(2.8), X(4.5), X(9), X(4.5), strokeColor=c, strokeWidth=X(1.5)))
            d.add(Line(X(9), X(4.5), X(15.2), X(4.5), strokeColor=c, strokeWidth=X(1.5)))
            d.add(Line(X(4.1), X(8.2), X(7.9), X(8.2), strokeColor=c, strokeWidth=X(1.3)))
            d.add(Line(X(10.1), X(8.2), X(13.9), X(8.2), strokeColor=c, strokeWidth=X(1.3)))
        elif tipo == "sensacion":
            pts = [
                X(9), X(17), X(10.6), X(11.3), X(16), X(9),
                X(10.6), X(6.7), X(9), X(1), X(7.4), X(6.7),
                X(2), X(9), X(7.4), X(11.3),
            ]
            d.add(Polygon(pts, strokeColor=c, fillColor=None, strokeWidth=X(1.4)))
        elif tipo == "elementos":
            d.add(Line(X(9), X(2), X(9), X(16), strokeColor=c, strokeWidth=X(2.2)))
            d.add(Line(X(2), X(9), X(16), X(9), strokeColor=c, strokeWidth=X(2.2)))
            d.add(Circle(X(9), X(9), X(6.5), strokeColor=c, fillColor=None, strokeWidth=X(1.1)))
        elif tipo == "colores":
            d.add(Circle(X(6), X(11), X(3.0), strokeColor=c, fillColor=None, strokeWidth=X(1.2)))
            d.add(Circle(X(11.8), X(11), X(3.0), strokeColor=c, fillColor=None, strokeWidth=X(1.2)))
            d.add(Circle(X(9), X(6), X(3.0), strokeColor=c, fillColor=None, strokeWidth=X(1.2)))
        elif tipo == "inspiracion":
            d.add(Circle(X(7.5), X(10.5), X(4.8), strokeColor=c, fillColor=None, strokeWidth=X(1.5)))
            d.add(Line(X(11), X(6.8), X(16), X(2), strokeColor=c, strokeWidth=X(1.8)))
        elif tipo == "notas":
            d.add(Rect(X(4), X(2), X(10), X(14), strokeColor=c, fillColor=None, strokeWidth=X(1.3)))
            d.add(Line(X(6), X(12), X(12), X(12), strokeColor=c, strokeWidth=X(1.0)))
            d.add(Line(X(6), X(9), X(12), X(9), strokeColor=c, strokeWidth=X(1.0)))
            d.add(Line(X(6), X(6), X(10.5), X(6), strokeColor=c, strokeWidth=X(1.0)))
        elif tipo == "datos":
            d.add(Rect(X(3), X(2), X(12), X(14), strokeColor=c, fillColor=None, strokeWidth=X(1.3)))
            for xx in (X(6), X(10.5)):
                for yy in (X(6), X(10.5)):
                    d.add(Rect(xx, yy, X(1.6), X(1.6), strokeColor=c, fillColor=None, strokeWidth=X(0.9)))
        elif tipo == "producto":
            d.add(Rect(X(6), X(4), X(6), X(9), strokeColor=c, fillColor=None, strokeWidth=X(1.3)))
            d.add(Rect(X(7.3), X(13), X(3.4), X(3), strokeColor=c, fillColor=None, strokeWidth=X(1.2)))
            d.add(Line(X(6), X(6.2), X(12), X(6.2), strokeColor=c, strokeWidth=X(0.9)))
        elif tipo == "diseno":
            pts = [X(9), X(16), X(11), X(11), X(16), X(9), X(11), X(7), X(9), X(2), X(7), X(7), X(2), X(9), X(7), X(11)]
            d.add(Polygon(pts, strokeColor=c, fillColor=None, strokeWidth=X(1.4)))
        elif tipo == "adjuntos":
            d.add(Rect(X(4), X(3), X(9), X(12), strokeColor=c, fillColor=None, strokeWidth=X(1.2)))
            d.add(Line(X(7), X(12), X(11), X(12), strokeColor=c, strokeWidth=X(1.0)))
            d.add(Line(X(7), X(9), X(11), X(9), strokeColor=c, strokeWidth=X(1.0)))
            d.add(Line(X(7), X(6), X(10), X(6), strokeColor=c, strokeWidth=X(1.0)))
        else:
            d.add(Circle(X(9), X(9), X(5.5), strokeColor=c, fillColor=None, strokeWidth=X(1.4)))

        return d

    def title_banner():
        t = Table(
            [
                [Paragraph("BRIEF DE DISEÑO", title_style)],
                [Paragraph("Edición Personalizada · Círculo Tequila", subtitle_style)],
            ],
            colWidths=[18.4 * cm],
        )
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PDF_RED),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
            ("TOPPADDING", (0, 1), (-1, 1), 0),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ]))
        return t

    def section_band(text, tipo="diseno"):
        t = Table(
            [[icono_pdf(tipo, "#FFFFFF", 15), Paragraph(text, sec_style)]],
            colWidths=[0.65 * cm, 17.75 * cm],
        )
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PDF_RED),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("LEFTPADDING", (0, 0), (0, 0), 5),
            ("RIGHTPADDING", (0, 0), (0, 0), 1),
            ("LEFTPADDING", (1, 0), (1, 0), 4),
            ("RIGHTPADDING", (1, 0), (1, 0), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def kv4_table(rows_4col, colWidths=(3.4 * cm, 5.8 * cm, 3.4 * cm, 5.8 * cm)):
        t = Table(rows_4col, colWidths=list(colWidths))
        s = [
            ("BOX", (0, 0), (-1, -1), 0.5, PDF_GREY_BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, PDF_GREY_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (0, -1), PDF_LIGHT_BG),
            ("BACKGROUND", (2, 0), (2, -1), PDF_LIGHT_BG),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        for i in range(len(rows_4col)):
            if i % 2 == 1:
                s.append(("BACKGROUND", (1, i), (1, i), PDF_GREY_ROW))
                s.append(("BACKGROUND", (3, i), (3, i), PDF_GREY_ROW))
        t.setStyle(TableStyle(s))
        return t

    def texto_bloque_visual(tipo, color_icono, titulo, contenido):
        contenido_p = Paragraph(texto_pdf_seguro(contenido), body_style)
        titulo_p = Paragraph(f"<b>{texto_pdf_seguro(titulo)}</b>", label_style)
        box = Table(
            [
                [icono_pdf(tipo, color_icono, 16), titulo_p],
                ["", contenido_p],
            ],
            colWidths=[0.78 * cm, 17.62 * cm],
        )
        box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, PDF_GREY_BORDER),
            ("BACKGROUND", (0, 0), (-1, 0), PDF_LIGHT_BG),
            ("SPAN", (0, 0), (0, 1)),
            ("VALIGN", (0, 0), (0, 1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 1), "CENTER"),
            ("LEFTPADDING", (0, 0), (0, 1), 6),
            ("RIGHTPADDING", (0, 0), (0, 1), 2),
            ("LEFTPADDING", (1, 0), (1, -1), 7),
            ("RIGHTPADDING", (1, 0), (1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("TOPPADDING", (0, 1), (-1, 1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
        ]))
        return box

    def preview_cell(archivo):
        preview = preparar_imagen_para_pdf(archivo["bytes"])
        rl_img = RLImage(io.BytesIO(preview))
        ratio = rl_img.imageWidth / rl_img.imageHeight

        max_w, max_h = 7.4 * cm, 4.8 * cm
        if ratio > (max_w / max_h):
            rl_img.drawWidth = max_w
            rl_img.drawHeight = max_w / ratio
        else:
            rl_img.drawHeight = max_h
            rl_img.drawWidth = max_h * ratio

        nombre_img = texto_pdf_seguro(archivo["nombre"])
        cell = Table(
            [[rl_img], [Paragraph(nombre_img, small_style)]],
            colWidths=[8.45 * cm],
        )
        cell.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.45, PDF_GREY_BORDER),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 1), (-1, 1), 3),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 5),
        ]))
        return cell

    def imagenes_seccion(titulo, archivos):
        """
        Presenta el material de referencia como miniaturas compactas.
        Los originales siguen incluidos completos dentro del ZIP.
        """
        imgs = [a for a in archivos if es_imagen(a["nombre"])]
        no_imgs = [a for a in archivos if not es_imagen(a["nombre"])]
        flowables = []

        if not archivos:
            return flowables

        flowables.append(Spacer(1, 0.16 * cm))
        flowables.append(section_band(
            f"MATERIAL DE REFERENCIA ({len(archivos)} archivo{'s' if len(archivos) != 1 else ''})",
            "adjuntos",
        ))
        flowables.append(Spacer(1, 0.12 * cm))

        celdas = []
        for archivo in imgs:
            try:
                celdas.append(preview_cell(archivo))
            except Exception:
                no_imgs.append(archivo)

        if celdas:
            rows = []
            span_last = False
            for i in range(0, len(celdas), 2):
                if i + 1 < len(celdas):
                    rows.append([celdas[i], celdas[i + 1]])
                else:
                    rows.append([celdas[i], ""])
                    span_last = True

            grid = Table(rows, colWidths=[9.2 * cm, 9.2 * cm], hAlign="CENTER")
            grid_style = [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
            if span_last:
                last_row = len(rows) - 1
                grid_style.extend([
                    ("SPAN", (0, last_row), (1, last_row)),
                    ("ALIGN", (0, last_row), (1, last_row), "CENTER"),
                ])
            grid.setStyle(TableStyle(grid_style))
            flowables.append(grid)

        if no_imgs:
            nombres = "<br/>".join(
                f"- {texto_pdf_seguro(a['nombre'])}" for a in no_imgs
            )
            otros = Table(
                [[Paragraph("<b>Otros archivos incluidos en el ZIP</b>", label_style)],
                 [Paragraph(nombres, file_list_style)]],
                colWidths=[18.4 * cm],
            )
            otros.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.5, PDF_GREY_BORDER),
                ("BACKGROUND", (0, 0), (-1, 0), PDF_LIGHT_BG),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            flowables.append(Spacer(1, 0.10 * cm))
            flowables.append(otros)

        flowables.append(Spacer(1, 0.12 * cm))
        return flowables

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.3 * cm,
        rightMargin=1.3 * cm,
        topMargin=0.8 * cm,
        bottomMargin=2.0 * cm,
    )
    story = []

    # Solapa compacta para A4: se conserva la imagen completa, sin estirarla.
    if solapa_path and solapa_path.exists():
        img = RLImage(str(solapa_path))
        max_w = 12.8 * cm
        max_h = 3.0 * cm
        ratio = img.imageWidth / img.imageHeight

        if ratio > (max_w / max_h):
            img.drawWidth = max_w
            img.drawHeight = max_w / ratio
        else:
            img.drawHeight = max_h
            img.drawWidth = max_h * ratio

        img.hAlign = "CENTER"
        story.append(img)
        story.append(Spacer(1, 0.12 * cm))

    story.append(title_banner())
    story.append(Spacer(1, 0.22 * cm))

    fecha_box = Table([[
        Paragraph("<b>FECHA DE ENVÍO</b>", label_style),
        Paragraph(
            f"<font size=10><b>{texto_pdf_seguro(datos['fecha'])}</b></font>",
            label_style,
        ),
    ]], colWidths=[3.3 * cm, 15.1 * cm])
    fecha_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, PDF_GREY_BORDER),
        ("BACKGROUND", (0, 0), (0, 0), PDF_LIGHT_BG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(fecha_box)
    story.append(Spacer(1, 0.24 * cm))

    story.append(section_band("DATOS CLIENTE / EMPRESA", "datos"))
    story.append(Spacer(1, 0.12 * cm))
    story.append(kv4_table([
        [L("Proyecto"), V(datos["nombre_proyecto"]), L("Contacto responsable"), V(datos["lider_nombre"])],
        [L("Celular"), V(datos["celular"]), L("Correo principal"), V(datos["correo"])],
        [L("Empresa"), V(datos["nombre_empresa"]), L("Correo adicional"), V(datos["correo_adicional"])],
        [L("Puesto"), V(datos["lider_puesto"]), L("Asesor"), V(datos["asesor_nombre"])],
        [L("Página web"), V(datos["pagina_web"]), L("Redes sociales"), V(datos["redes_sociales"])],
    ]))

    story.append(Spacer(1, 0.24 * cm))
    story.append(section_band("PRESENTACIÓN DEL PRODUCTO", "producto"))
    story.append(Spacer(1, 0.12 * cm))
    story.append(kv4_table([
        [
            L("375 ml"),
            V("Seleccionada" if datos["presentacion_375"] else "No seleccionada"),
            L("750 ml"),
            V("Seleccionada" if datos["presentacion_750"] else "No seleccionada"),
        ],
    ]))

    story.append(Spacer(1, 0.24 * cm))
    story.append(section_band("CARACTERÍSTICAS DEL DISEÑO", "diseno"))
    story.append(Spacer(1, 0.12 * cm))

    story.append(
        texto_bloque_visual(
            "diseno",
            "#252525",
            "Describe cómo imaginas tu diseño",
            datos["caracteristicas_diseno"],
        )
    )
    story.append(Spacer(1, 0.09 * cm))
    story.append(
        texto_bloque_visual(
            "notas",
            "#76538F",
            "Notas / comentarios",
            datos["informacion_adicional"],
        )
    )

    for titulo, archivos in adjuntos_por_seccion.items():
        story.extend(imagenes_seccion(titulo, archivos))

    story.append(Spacer(1, 0.16 * cm))

    lider_pdf = texto_pdf_seguro(datos["lider_nombre"])
    correo_pdf = texto_pdf_seguro(datos["correo"])
    fecha_pdf = texto_pdf_seguro(datos["fecha"])

    aceptacion = Table(
        [[Paragraph(
            f"<i>Brief confirmado digitalmente por <b>{lider_pdf}</b> "
            f"({correo_pdf}) el {fecha_pdf}. La información y los archivos adjuntos "
            f"se proporcionan para el desarrollo del diseño solicitado.</i>",
            body_style,
        )]],
        colWidths=[18.4 * cm],
    )
    aceptacion.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, PDF_GREY_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), PDF_LIGHT_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(aceptacion)

    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args,
            proyecto=datos["nombre_proyecto"],
            empresa=datos["nombre_empresa"],
            **kwargs,
        ),
    )

    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# =========================================================
# Empaquetado de adjuntos (.zip) y envío de correo
# =========================================================
def build_zip_bytes(
    pdf_bytes: bytes,
    pdf_name: str,
    adjuntos_por_seccion: dict,
) -> bytes:
    """Crea un ZIP con el PDF y todos los archivos originales."""
    buffer = io.BytesIO()
    rutas_usadas: set[str] = set()

    def ruta_unica(carpeta: str, nombre: str) -> str:
        carpeta_segura = nombre_archivo_seguro(carpeta, "Adjuntos")
        nombre_seguro = nombre_archivo_seguro(nombre)
        base = Path(nombre_seguro).stem
        sufijo = Path(nombre_seguro).suffix
        candidato = f"{carpeta_segura}/{nombre_seguro}"
        contador = 2

        while candidato.lower() in rutas_usadas:
            candidato = f"{carpeta_segura}/{base}_{contador}{sufijo}"
            contador += 1

        rutas_usadas.add(candidato.lower())
        return candidato

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as zf:
        pdf_seguro = nombre_archivo_seguro(pdf_name, "Brief.pdf")
        zf.writestr(pdf_seguro, pdf_bytes)
        rutas_usadas.add(pdf_seguro.lower())

        for carpeta, archivos in adjuntos_por_seccion.items():
            for archivo in archivos:
                zf.writestr(
                    ruta_unica(carpeta, archivo["nombre"]),
                    archivo["bytes"],
                )

    return buffer.getvalue()


def get_smtp_config():
    try:
        smtp_cfg = st.secrets["smtp"]
        brief_cfg = st.secrets["brief"]
        return {
            "host": smtp_cfg["host"],
            "port": int(smtp_cfg.get("port", 465)),
            "user": smtp_cfg["user"],
            "password": smtp_cfg["password"],
            "from_name": smtp_cfg.get("from_name", "Brief de Diseño · Círculo Tequila"),
            "to_email": brief_cfg["to_email"],
        }
    except Exception:
        return None


def enviar_correo(
    datos: dict,
    zip_bytes: bytes,
    zip_name: str,
) -> tuple[bool, str]:
    """Envía el mismo paquete ZIP a Diseño, cliente(s) y asesor mediante SMTP SSL."""
    cfg = get_smtp_config()

    if cfg is None:
        return False, (
            "El envío automático aún no está configurado. "
            "Descarga el paquete ZIP y compártelo manualmente con el equipo de Diseño."
        )

    limite_zip_bytes = TAMANO_MAX_ZIP_CORREO_MB * 1024 * 1024
    if len(zip_bytes) > limite_zip_bytes:
        return False, (
            f"El paquete ZIP pesa {tam_legible(len(zip_bytes))} y supera el límite "
            f"de {TAMANO_MAX_ZIP_CORREO_MB} MB para envío automático. "
            "Descárgalo y compártelo manualmente con el equipo de Diseño."
        )

    destinatarios_diseno = [
        correo_destino.strip()
        for correo_destino in str(cfg["to_email"]).split(",")
        if correo_destino.strip()
    ]
    if not destinatarios_diseno:
        return False, "No hay destinatarios configurados en [brief].to_email."

    # Cliente principal + correo adicional + asesor registrado.
    destinatarios_copia = []

    if es_correo_valido(datos["correo"]):
        destinatarios_copia.append(datos["correo"])

    if datos.get("correo_adicional") and es_correo_valido(datos["correo_adicional"]):
        destinatarios_copia.append(datos["correo_adicional"])

    if datos.get("asesor_correo") and es_correo_valido(datos["asesor_correo"]):
        destinatarios_copia.append(datos["asesor_correo"])

    # Evita correos duplicados, conservando el orden.
    diseno_lower = {correo_destino.lower() for correo_destino in destinatarios_diseno}
    vistos = set()
    bcc = []
    for correo_destino in destinatarios_copia:
        clave = correo_destino.lower()
        if clave not in vistos and clave not in diseno_lower:
            bcc.append(correo_destino)
            vistos.add(clave)

    msg = EmailMessage()
    empresa_asunto = f"{datos['nombre_empresa']} · " if datos["nombre_empresa"] else ""
    msg["Subject"] = f"Brief de Diseño | {empresa_asunto}{datos['nombre_proyecto']}"
    msg["From"] = f"{cfg['from_name']} <{cfg['user']}>"
    msg["To"] = ", ".join(destinatarios_diseno)
    msg["Reply-To"] = datos["correo"]

    puesto_txt = f" ({datos['lider_puesto']})" if datos["lider_puesto"] else ""
    empresa_txt = datos["nombre_empresa"] or "No especificada"
    correo_adicional_txt = datos["correo_adicional"] or "No especificado"
    asesor_txt = datos["asesor_nombre"] or "No especificado"

    cuerpo = f"""¡Gracias por compartir este proyecto con Círculo Tequila!

La información y los archivos del brief fueron enviados correctamente y ya están disponibles para su revisión.

Proyecto: {datos['nombre_proyecto']}
Contacto responsable: {datos['lider_nombre']}{puesto_txt}
Celular: {datos['celular']}
Correo principal: {datos['correo']}
Correo adicional: {correo_adicional_txt}
Empresa: {empresa_txt}
Asesor: {asesor_txt}

En el archivo ZIP adjunto encontrarás el Brief de Diseño en PDF, junto con el material de referencia proporcionado para el desarrollo del proyecto.

Este material será la base para que nuestro equipo de Diseño conozca la idea, las referencias y los elementos importantes del proyecto.

Gracias por confiar en Círculo Tequila para crear una edición especial.

Este correo fue generado automáticamente desde nuestro Brief de Diseño."""
    msg.set_content(cuerpo)
    msg.add_attachment(
        zip_bytes,
        maintype="application",
        subtype="zip",
        filename=zip_name,
    )

    try:
        with smtplib.SMTP_SSL(
            cfg["host"],
            cfg["port"],
            timeout=30,
        ) as server:
            server.login(cfg["user"], cfg["password"])
            server.send_message(
                msg,
                to_addrs=destinatarios_diseno + bcc,
            )

        return True, (
            "✅ Tu brief y sus archivos se enviaron correctamente "
            "al equipo de Diseño y a los correos correspondientes."
        )
    except Exception as error:
        return False, (
            f"No se pudo enviar el correo automáticamente "
            f"({type(error).__name__}: {error}). "
            "Descarga el paquete ZIP y compártelo manualmente con el equipo de Diseño."
        )

# =========================================================
# Pantalla de éxito (después de enviar)
# =========================================================
if st.session_state.submitted:
    res = st.session_state.submit_result
    email_ok = bool(res.get("email_ok"))

    if email_ok:
        st.success(res.get("email_msg", "✅ Brief enviado correctamente."))
        empresa_res = str(res.get("nombre_empresa", "") or "").strip()
        proyecto_res = escape(str(res.get("nombre_proyecto", "")))
        lider_res = escape(str(res.get("lider_nombre", "")))

        if empresa_res:
            mensaje_final = (
                f"<b>¡Gracias, {lider_res}! 🎉</b><br/>"
                f"Recibimos el brief de <b>{escape(empresa_res)}</b> "
                f"para el proyecto <b>{proyecto_res}</b>. "
                "El equipo de diseño de Círculo Tequila lo revisará y se pondrá "
                "en contacto contigo a la brevedad."
            )
        else:
            mensaje_final = (
                f"<b>¡Gracias, {lider_res}! 🎉</b><br/>"
                f"Recibimos el brief para el proyecto <b>{proyecto_res}</b>. "
                "El equipo de diseño de Círculo Tequila lo revisará y se pondrá "
                "en contacto contigo a la brevedad."
            )
    else:
        st.warning(res.get(
            "email_msg",
            "No se pudo enviar el correo automáticamente.",
        ))
        mensaje_final = (
            "<b>El paquete fue generado correctamente, pero no se confirmó su envío "
            "por correo.</b><br/>Descarga el ZIP y compártelo manualmente con el equipo de Diseño."
        )

    st.markdown(
        f'<div class="intro-card">{mensaje_final}</div>',
        unsafe_allow_html=True,
    )

    colD1, colD2 = st.columns(2)
    with colD1:
        st.download_button(
            "⬇️ Descargar copia del brief (PDF)",
            data=res["pdf_bytes"],
            file_name=res["pdf_name"],
            mime="application/pdf",
            use_container_width=True,
        )
    with colD2:
        st.download_button(
            "⬇️ Descargar paquete completo (.zip)",
            data=res["zip_bytes"],
            file_name=res["zip_name"],
            mime="application/zip",
            use_container_width=True,
        )

    st.markdown("---")
    if st.button("📝 Llenar otro brief", use_container_width=True):
        reiniciar_formulario()
        st.rerun()

    st.stop()


# =========================================================
# Introducción / instrucciones (didáctico y amigable)
# =========================================================
st.markdown(
    """
    <div class="intro-card">
        👋 <b>¡Hola! Este Brief nos ayudará a comprender con mayor claridad lo que deseas comunicar y plasmar en tu diseño, para desarrollar una propuesta precisa y alineada a lo que tienes en mente.</b><br/>
        Por favor, completa la información solicitada con el mayor detalle posible. Los campos marcados con <b>*</b> son obligatorios.</div>""",
    unsafe_allow_html=True,
)


if SPIN_EJEMPLOS:
    with st.expander("Conoce algunos diseños", expanded=True):
        st.caption(
            "Estos son algunos diseños que ya creamos para otros clientes que pueden servir como referencia e inspiración para el desarrollo de tu diseño. "
        )

        st.markdown("##### 🔄 Ejemplos interactivos 360°")
        st.caption(
            "Haz clic sobre cada vista y arrastra la botella para visualizar el diseño completo."
        )

        cols_spin = st.columns(3)
        for i, item in enumerate(SPIN_EJEMPLOS):
            with cols_spin[i % 3]:
                with st.container(border=True):
                    st.iframe(
                        item["url"],
                        height=260,
                        width="stretch",
                    )


_gen = st.session_state.form_gen

with st.sidebar:
    st.markdown(
        f"""
        <div style="text-align:center; padding:8px 0 12px 0;">
            <div style="font-weight:700; color:{PRIMARY}; font-size:1rem;">
                Círculo Tequila
            </div>
            <div style="font-size:0.78rem; color:#666;">
                Brief de Diseño · Marketing
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("##### 💡 Antes de adjuntar tus archivos")
    st.caption(
        "• Fotos/imágenes: procura utilizar archivos de buena calidad.\n\n"
        "• Puedes adjuntar fotografías, ilustraciones, manuales, PDFs o referencias "
        "que ayuden a nuestro equipo de diseño a entender mejor tu idea.\n\n"
        f"• El tamaño máximo total permitido para los archivos adjuntos es de "
        f"{TAMANO_MAX_ADJUNTOS_MB} MB."
    )
    st.markdown("---")
    st.caption(f"📅 {fecha_es(ahora_mexico())}")


# =========================================================
# Datos Cliente / Empresa
# =========================================================
section_header("🏢 Datos Cliente / Empresa")

with st.container(border=True):
    col1, col2 = st.columns(2)

    with col1:
        nombre_proyecto = st.text_input(
            "Nombre del proyecto *",
            placeholder="Ej. Aniversario 25 años",
            key=f"nombre_proyecto_{_gen}",
        )
    with col2:
        lider_nombre = st.text_input(
            "Contacto responsable de Proyecto *",
            placeholder="Nombre completo",
            key=f"lider_nombre_{_gen}",
        )

    col3, col4 = st.columns(2)
    with col3:
        celular = st.text_input(
            "Celular *",
            placeholder="Ej. 33 1234 5678",
            key=f"celular_{_gen}",
        )
    with col4:
        correo = st.text_input(
            "Correo principal *",
            placeholder="nombre@empresa.com",
            key=f"correo_{_gen}",
        )

    col5, col6 = st.columns(2)
    with col5:
        nombre_empresa = st.text_input(
            "Nombre de la empresa",
            placeholder="Opcional",
            key=f"nombre_empresa_{_gen}",
        )
    with col6:
        correo_adicional = st.text_input(
            "Correo adicional",
            placeholder="Opcional",
            key=f"correo_adicional_{_gen}",
        )

    col7, col8 = st.columns(2)
    with col7:
        lider_puesto = st.text_input(
            "Puesto",
            placeholder="Opcional — Ej. Gerente Comercial",
            key=f"lider_puesto_{_gen}",
        )
    with col8:
        asesor_sel = st.selectbox(
            "Asesor que te atendió *",
            options=list(ASESORES.keys()) + [ASESOR_OTRO],
            index=None,
            placeholder="Selecciona una opción",
            key=f"asesor_sel_{_gen}",
        )

        asesor_otro = ""
        if asesor_sel == ASESOR_OTRO:
            asesor_otro = st.text_input(
                "Nombre de la persona que te atendió *",
                placeholder="Escribe su nombre",
                key=f"asesor_otro_{_gen}",
            )

    asesor_nombre = (
        asesor_otro.strip()
        if asesor_sel == ASESOR_OTRO
        else (asesor_sel or "")
    )
    asesor_correo = ASESORES.get(asesor_sel, "") if asesor_sel else ""

    col9, col10 = st.columns(2)
    with col9:
        pagina_web = st.text_input(
            "Página web",
            placeholder="https://tuempresa.com",
            key=f"pagina_web_{_gen}",
        )
    with col10:
        redes_sociales = st.text_input(
            "Redes sociales",
            placeholder="@tuempresa",
            key=f"redes_sociales_{_gen}",
        )

# =========================================================
# Presentación del producto
# =========================================================
section_header(
    "🍶 Presentación del producto",
)

with st.container(border=True):
    st.caption(
        "Selecciona una o ambas presentaciones. Esto nos ayudará a considerar el espacio disponible y adaptar correctamente tu diseño. "
    )

    colv1, colv2 = st.columns(2)

    with colv1:
        presentacion_375 = st.checkbox(
            "375 ml",
            key=f"presentacion_375_{_gen}"
        )

    with colv2:
        presentacion_750 = st.checkbox(
            "750 ml",
            key=f"presentacion_750_{_gen}"
        )


# =========================================================
# Características del diseño — PROPUESTA MKT
# =========================================================
section_header("🎨 Características del diseño")

st.markdown(
    """
    <div class="intro-card" style="margin-bottom:0.8rem;">
        Cuéntanos libremente cómo imaginas tu diseño. Comparte toda la información
        que consideres importante para que nuestro equipo pueda entender tu idea.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.container(border=True):
    caracteristicas_diseno = st.text_area(
        "Describe cómo imaginas tu diseño *",
        placeholder=(
            "Escribe aquí todo lo que consideres importante sobre tu idea, "
            "concepto, estilo, colores, elementos, referencias, mensajes o "
            "cualquier detalle que quieras que tomemos en cuenta."
        ),
        height=280,
        key=f"caracteristicas_diseno_{_gen}"
    )

    st.markdown("#### 📎 Adjunta tus archivos *")

    st.caption(
        "Adjunta cualquier material que pueda ayudarnos a desarrollar tu idea: "
        "imágenes, fotografías, ilustraciones, textos, identidad gráfica, manuales, "
        "referencias visuales, PDFs o archivos vectoriales, según aplique a tu proyecto."
    )

    adjuntos_files = st.file_uploader(
        "Adjuntar archivos",
        type=TIPOS_ADJUNTOS_PERMITIDOS,
        accept_multiple_files=True,
        key=f"adjuntos_files_{_gen}"
    )

    if adjuntos_files:
        cols_adjuntos = st.columns(4)

        for fi, f in enumerate(adjuntos_files):
            with cols_adjuntos[fi % 4]:
                if es_imagen(f.name):
                    st.image(
                        f.getvalue(),
                        caption=f.name,
                        width=160
                    )
                else:
                    st.info(f"📎 {f.name}")

    st.markdown("#### 📝 Notas / comentarios")

    informacion_adicional = st.text_area(
        "Notas / comentarios",
        placeholder="Opcional",
        height=100,
        key=f"informacion_adicional_{_gen}"
    )

# =========================================================
# Validación de tamaño de adjuntos
# =========================================================
todos_los_archivos = list(adjuntos_files or [])
peso_total = sum(
    len(archivo.getvalue())
    for archivo in todos_los_archivos
)

peso_total_excedido = (
    peso_total > TAMANO_MAX_ADJUNTOS_MB * 1024 * 1024
)

if peso_total_excedido:
    st.error(
        f"⚠️ Los archivos seleccionados pesan {tam_legible(peso_total)} en total. "
        f"El máximo permitido es {TAMANO_MAX_ADJUNTOS_MB} MB. "
        "Elimina algunos archivos o reduce su tamaño para poder enviar el brief."
    )
elif peso_total > 0:
    st.caption(
        f"📎 Archivos seleccionados: {len(todos_los_archivos)} · "
        f"Peso total: {tam_legible(peso_total)} de "
        f"{TAMANO_MAX_ADJUNTOS_MB} MB permitidos."
    )
st.markdown(
    """
    <div style="
        background:#FFF7F7;
        border:1px solid #E7CACA;
        border-left:5px solid #C0392B;
        padding:15px 18px;
        border-radius:8px;
        margin-top:20px;
        margin-bottom:20px;
        font-size:0.96rem;
        line-height:1.45;
        color:#333333;
        box-shadow:0 1px 4px rgba(0,0,0,0.05);
    ">
        <div style="
            font-weight:700;
            font-size:1rem;
            margin-bottom:4px;
            color:#9B2C24;
        ">
            ⚠️ Aviso sobre colores y acabados
        </div>
        <div>
            Ten en cuenta que los colores y acabados pueden presentar ligeras variaciones
            una vez impresos sobre la botella, por lo que el resultado final puede diferir
            ligeramente de lo visualizado en pantalla.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Aceptación y envío
# =========================================================
section_header("✅ Confirmación y envío")

with st.container(border=True):
    st.caption(
        "Al enviar el brief, el mismo material se compartirá automáticamente con "
        "el equipo de Diseño, el correo principal, el correo adicional (si se capturó) "
        "y el asesor registrado."
    )
    acepto = st.checkbox(
        "Confirmo que la información y archivos proporcionados son correctos y autorizo a "
        "Círculo Tequila a utilizarlos para desarrollar el diseño solicitado. *",
        key=f"acepto_{_gen}"
    )

# Validaciones
errores = []
campos_requeridos = {
    "Nombre del proyecto": nombre_proyecto,
    "Contacto responsable del proyecto": lider_nombre,
    "Celular": celular,
    "Características del diseño": caracteristicas_diseno,
}
for etiqueta, valor in campos_requeridos.items():
    if not valor.strip():
        errores.append(f"• {etiqueta}")

if not correo.strip():
    errores.append("• Correo principal")
elif not es_correo_valido(correo):
    errores.append("• Correo principal (formato no válido)")

if correo_adicional.strip() and not es_correo_valido(correo_adicional):
    errores.append("• Correo adicional (formato no válido)")

if not asesor_sel:
    errores.append("• Asesor que te atendió")
elif asesor_sel == ASESOR_OTRO and not asesor_otro.strip():
    errores.append("• Nombre de la persona que te atendió")

if not presentacion_375 and not presentacion_750:
    errores.append("• Selecciona al menos una presentación: 375 ml o 750 ml")

if peso_total_excedido:
    errores.append(
        f"• Los archivos adjuntos superan el límite total de "
        f"{TAMANO_MAX_ADJUNTOS_MB} MB"
    )

if not adjuntos_files:
    errores.append("• Adjunta tus archivos")

if not acepto:
    errores.append("• Debes confirmar la casilla de aceptación")

puede_enviar = len(errores) == 0

if errores:
    st.warning("⚠️ Antes de enviar, revisa lo siguiente:\n\n" + "\n".join(errores))

if st.button(
    "📩 Enviar brief",
    type="primary",
    disabled=not puede_enviar,
    use_container_width=True,
):
    datos = {
        "fecha": fecha_es(ahora_mexico()),
        "nombre_empresa": nombre_empresa.strip(),
        "nombre_proyecto": nombre_proyecto.strip(),
        "pagina_web": pagina_web.strip(),
        "redes_sociales": redes_sociales.strip(),
        "lider_nombre": lider_nombre.strip(),
        "lider_puesto": lider_puesto.strip(),
        "celular": celular.strip(),
        "correo": correo.strip(),
        "correo_adicional": correo_adicional.strip(),
        "asesor_nombre": asesor_nombre.strip(),
        "asesor_correo": asesor_correo.strip(),
        "presentacion_375": bool(presentacion_375),
        "presentacion_750": bool(presentacion_750),
        "caracteristicas_diseno": caracteristicas_diseno.strip(),
        "informacion_adicional": informacion_adicional.strip(),
    }

    adjuntos_por_seccion = {
        "Material de referencia": [
            {"nombre": f.name, "bytes": f.getvalue()}
            for f in (adjuntos_files or [])
        ],
    }

    proyecto_archivo = nombre_archivo_seguro(
        datos["nombre_proyecto"],
        "Proyecto",
    )

    if datos["nombre_empresa"]:
        empresa_archivo = nombre_archivo_seguro(
            datos["nombre_empresa"],
            "Empresa",
        )
        nombre_base = f"{empresa_archivo}_{proyecto_archivo}"
    else:
        nombre_base = proyecto_archivo

    pdf_name = f"Brief_{nombre_base}.pdf"
    zip_name = f"Paquete_Brief_{nombre_base}.zip"

    try:
        with st.spinner(
            "Generando el PDF, preparando los archivos y enviándolos al equipo de Diseño..."
        ):
            pdf_bytes = build_brief_pdf(
                datos,
                adjuntos_por_seccion,
            )
            zip_bytes = build_zip_bytes(
                pdf_bytes,
                pdf_name,
                adjuntos_por_seccion,
            )
            email_ok, email_msg = enviar_correo(
                datos,
                zip_bytes,
                zip_name,
            )
    except Exception as error:
        st.error(
            "No fue posible generar el paquete del brief. "
            "Revisa los archivos adjuntos e inténtalo nuevamente."
        )
        st.caption(f"Detalle técnico: {type(error).__name__}: {error}")
        st.stop()

    st.session_state.submit_result = {
        "email_ok": email_ok,
        "email_msg": email_msg,
        "pdf_bytes": pdf_bytes,
        "pdf_name": pdf_name,
        "zip_bytes": zip_bytes,
        "zip_name": zip_name,
        "lider_nombre": datos["lider_nombre"],
        "nombre_empresa": datos["nombre_empresa"],
        "nombre_proyecto": datos["nombre_proyecto"],
    }
    st.session_state.submitted = True
    st.rerun()
