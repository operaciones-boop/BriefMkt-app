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
from PIL import Image as PILImage, ImageOps


# =========================================================
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
    .stAlert {{ border-radius: 8px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

MESES_ES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO",
    7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

ESTILOS_SUGERIDOS = [
    "Tradicional mexicano",
    "Minimalista",
    "Corporativo",
    "Artístico / Ilustrado",
    "Elegante / Premium",
    "Moderno / Geométrico",
    "Otro (especifica)",
]

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
]
def section_header(title: str, sub: str = ""):
    sub_html = f'<span class="sub"> · {sub}</span>' if sub else ""
    st.markdown(
        f'<div class="section-header"><h3>{title}{sub_html}</h3></div>',
        unsafe_allow_html=True,
    )


def bold_unicode(text: str) -> str:
    """Convierte letras/números ASCII a Unicode 'Mathematical Bold', para
    resaltar visualmente una opción dentro de un st.selectbox."""
    out = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            out.append(chr(0x1D400 + (ord(ch) - ord('A'))))
        elif 'a' <= ch <= 'z':
            out.append(chr(0x1D41A + (ord(ch) - ord('a'))))
        elif '0' <= ch <= '9':
            out.append(chr(0x1D7CE + (ord(ch) - ord('0'))))
        else:
            out.append(ch)
    return ''.join(out)


def formato_opcion_estilo(opt: str) -> str:
    if opt == "Otro (especifica)":
        return f"✏️ {bold_unicode(opt.upper())}"
    return opt


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
    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    title_style = ParagraphStyle("title_style", parent=styles["Title"],
        fontName="Helvetica-Bold", fontSize=18, textColor=colors.white,
        alignment=TA_CENTER, spaceAfter=0, leading=22)
    subtitle_style = ParagraphStyle("subtitle_style", parent=normal,
        fontName="Helvetica", fontSize=8.5, textColor=colors.white,
        alignment=TA_CENTER, leading=10)
    sec_style = ParagraphStyle("sec_style", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=11, textColor=colors.white,
        spaceBefore=0, spaceAfter=0, leading=14, alignment=TA_LEFT)
    label_style = ParagraphStyle("label_style", parent=normal,
        fontName="Helvetica", fontSize=9, textColor=PDF_TEXT, leading=12)
    value_style = ParagraphStyle("value_style", parent=normal,
        fontName="Helvetica-Bold", fontSize=9.5, textColor=PDF_RED_DARK, leading=12)
    body_style = ParagraphStyle("body_style", parent=normal,
        fontName="Helvetica", fontSize=9.3, textColor=PDF_TEXT, leading=13)
    img_caption_style = ParagraphStyle("img_caption_style", parent=normal,
        fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, leading=11)

    def L(txt):
        return Paragraph(str(txt), label_style)

    def V(txt):
        return Paragraph(
            f"<b>{texto_pdf_seguro(txt)}</b>",
            value_style,
        )

    def title_banner():
        t = Table([[Paragraph("BRIEF DE DISEÑO", title_style)],
                   [Paragraph("Edición Personalizada · Círculo Tequila", subtitle_style)]],
                  colWidths=[18.4 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PDF_RED),
            ("TOPPADDING", (0, 0), (-1, 0), 12), ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
            ("TOPPADDING", (0, 1), (-1, 1), 0), ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ]))
        return t

    def section_band(text):
        t = Table([[Paragraph(text, sec_style)]], colWidths=[18.4 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PDF_RED),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def kv4_table(rows_4col, colWidths=(3.4 * cm, 5.8 * cm, 3.4 * cm, 5.8 * cm)):
        t = Table(rows_4col, colWidths=list(colWidths))
        s = [("BOX", (0, 0), (-1, -1), 0.5, PDF_GREY_BORDER),
             ("INNERGRID", (0, 0), (-1, -1), 0.3, PDF_GREY_BORDER),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 9),
             ("BACKGROUND", (0, 0), (0, -1), PDF_LIGHT_BG), ("BACKGROUND", (2, 0), (2, -1), PDF_LIGHT_BG),
             ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
        for i in range(len(rows_4col)):
            if i % 2 == 1:
                s.append(("BACKGROUND", (1, i), (1, i), PDF_GREY_ROW))
                s.append(("BACKGROUND", (3, i), (3, i), PDF_GREY_ROW))
        t.setStyle(TableStyle(s))
        return t

    def texto_bloque(titulo, contenido):
        box = Table([[Paragraph(f"<b>{titulo}</b>", label_style)], [_P(contenido, body_style)]],
                     colWidths=[18.4 * cm])
        box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, PDF_GREY_BORDER),
            ("BACKGROUND", (0, 0), (-1, 0), PDF_LIGHT_BG),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return box

    def imagenes_seccion(titulo, archivos):
        """Agrega vistas previas de imágenes al PDF y lista los demás archivos."""
        imgs = [a for a in archivos if es_imagen(a["nombre"])]
        no_imgs = [a for a in archivos if not es_imagen(a["nombre"])]
        flowables = []

        if not archivos:
            return flowables

        cap_tbl = Table(
            [[Paragraph(
                f"ADJUNTOS — {texto_pdf_seguro(titulo)} ({len(archivos)})",
                img_caption_style,
            )]],
            colWidths=[18.4 * cm],
        )
        cap_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PDF_RED_DARK),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        flowables.append(Spacer(1, 0.15 * cm))
        flowables.append(cap_tbl)

        max_w, max_h = 16.0 * cm, 9.0 * cm

        for archivo in imgs:
            try:
                preview = preparar_imagen_para_pdf(archivo["bytes"])
                rl_img = RLImage(io.BytesIO(preview))
                ratio = rl_img.imageWidth / rl_img.imageHeight

                if ratio > (max_w / max_h):
                    rl_img.drawWidth = max_w
                    rl_img.drawHeight = max_w / ratio
                else:
                    rl_img.drawHeight = max_h
                    rl_img.drawWidth = max_h * ratio

                nombre_img = texto_pdf_seguro(archivo["nombre"])
                img_wrap = Table(
                    [[rl_img], [Paragraph(nombre_img, label_style)]],
                    colWidths=[18.4 * cm],
                )
                img_wrap.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("BOX", (0, 0), (-1, -1), 0.5, PDF_GREY_BORDER),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
                ]))
                flowables.append(img_wrap)
                flowables.append(Spacer(1, 0.10 * cm))
            except Exception:
                no_imgs.append(archivo)

        if no_imgs:
            nombres = texto_pdf_seguro(
                ", ".join(a["nombre"] for a in no_imgs)
            )
            flowables.append(Paragraph(
                f"<i>Otros archivos incluidos en el paquete ZIP: {nombres}</i>",
                body_style,
            ))
            flowables.append(Spacer(1, 0.1 * cm))

        flowables.append(Spacer(1, 0.1 * cm))
        return flowables

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        leftMargin=1.3 * cm, rightMargin=1.3 * cm, topMargin=1.0 * cm, bottomMargin=2.0 * cm)
    story = []

    if solapa_path and solapa_path.exists():
        max_width = 18.5 * cm
        img = RLImage(str(solapa_path))
        img.drawWidth = max_width
        img.drawHeight = img.imageHeight * max_width / img.imageWidth
        story.append(img)
        story.append(Spacer(1, 0.18 * cm))

    story.append(title_banner())
    story.append(Spacer(1, 0.30 * cm))

    fecha_box = Table([[
        Paragraph("FECHA<br/><font size=7 color='#666'>de envío</font>", label_style),
        Paragraph(f"<font size=11><b>{texto_pdf_seguro(datos['fecha'])}</b></font>", label_style),
    ]], colWidths=[3.0 * cm, 15.4 * cm])
    fecha_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, PDF_RED), ("BACKGROUND", (0, 0), (0, 0), PDF_LIGHT_BG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(fecha_box)
    story.append(Spacer(1, 0.30 * cm))

    story.append(section_band("DATOS CLIENTE / EMPRESA"))
    story.append(Spacer(1, 0.15 * cm))
    story.append(kv4_table([
        [L("Proyecto"), V(datos["nombre_proyecto"]), L("Contacto responsable"), V(datos["lider_nombre"])],
        [L("Celular"), V(datos["celular"]), L("Correo"), V(datos["correo"])],
        [L("Empresa"), V(datos["nombre_empresa"]), L("Puesto"), V(datos["lider_puesto"])],
        [L("Página web"), V(datos["pagina_web"]), L("Redes sociales"), V(datos["redes_sociales"])],
    ]))

    story.append(Spacer(1, 0.30 * cm))
    story.append(section_band("PRESENTACIÓN DEL PRODUCTO"))
    story.append(Spacer(1, 0.15 * cm))
    story.append(kv4_table([
        [
            L("375 ml"),
            V("Seleccionada" if datos["presentacion_375"] else "No seleccionada"),
            L("750 ml"),
            V("Seleccionada" if datos["presentacion_750"] else "No seleccionada"),
        ],
    ]))

    story.append(Spacer(1, 0.30 * cm))
    story.append(section_band("CARACTERÍSTICAS DEL DISEÑO"))
    story.append(Spacer(1, 0.15 * cm))
    story.append(texto_bloque("Objetivo del diseño / Mensaje a comunicar", datos["objetivo_diseno"]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(kv4_table([
        [
            L("Frase o eslogan"),
            V(datos["frase_eslogan"]),
            L("Estilo deseado"),
            V(datos["estilo_deseado"]),
        ],
    ]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(texto_bloque("Colores sugeridos", datos["paleta_colores"]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(texto_bloque("Iconografía o símbolos relevantes", datos["iconografia"]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(texto_bloque("Elementos gráficos a incluir", datos["elementos_graficos"]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(texto_bloque("Herramientas / referencias visuales (notas)", datos["herramientas_notas"]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(texto_bloque("Notas / comentarios", datos["informacion_adicional"]))

    for titulo, archivos in adjuntos_por_seccion.items():
        story.extend(imagenes_seccion(titulo, archivos))

    story.append(Spacer(1, 0.3 * cm))

    lider_pdf = texto_pdf_seguro(datos["lider_nombre"])
    correo_pdf = texto_pdf_seguro(datos["correo"])
    fecha_pdf = texto_pdf_seguro(datos["fecha"])

    aceptacion = Table([[Paragraph(
        f"<i>Brief confirmado digitalmente por <b>{lider_pdf}</b> "
        f"({correo_pdf}) el {fecha_pdf}. El material gráfico adjunto "
        f"se entrega para uso exclusivo de diseño de este proyecto.</i>",
        body_style)]], colWidths=[18.4 * cm])
    aceptacion.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, PDF_GREY_BORDER), ("BACKGROUND", (0, 0), (-1, -1), PDF_LIGHT_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(aceptacion)

    doc.build(story, canvasmaker=lambda *args, **kwargs: NumberedCanvas(
        *args, proyecto=datos["nombre_proyecto"], empresa=datos["nombre_empresa"], **kwargs))
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
    copia_cliente: bool,
) -> tuple[bool, str]:
    """Envía únicamente el paquete ZIP mediante SMTP SSL."""
    cfg = get_smtp_config()

    if cfg is None:
        return False, (
            "El envío automático aún no está configurado. "
            "Descarga el paquete ZIP y compártelo manualmente con Marketing."
        )

    limite_zip_bytes = TAMANO_MAX_ZIP_CORREO_MB * 1024 * 1024
    if len(zip_bytes) > limite_zip_bytes:
        return False, (
            f"El paquete ZIP pesa {tam_legible(len(zip_bytes))} y supera el límite "
            f"de {TAMANO_MAX_ZIP_CORREO_MB} MB para envío automático. "
            "Descárgalo y compártelo manualmente con Marketing."
        )

    destinatarios = [
        correo.strip()
        for correo in str(cfg["to_email"]).split(",")
        if correo.strip()
    ]
    if not destinatarios:
        return False, "No hay destinatarios configurados en [brief].to_email."

    bcc = []
    if copia_cliente and es_correo_valido(datos["correo"]):
        bcc.append(datos["correo"])

    msg = EmailMessage()
    empresa_asunto = f"{datos['nombre_empresa']} — " if datos["nombre_empresa"] else ""
    msg["Subject"] = f"Brief de Diseño · {empresa_asunto}{datos['nombre_proyecto']}"
    msg["From"] = f"{cfg['from_name']} <{cfg['user']}>"
    msg["To"] = ", ".join(destinatarios)
    msg["Reply-To"] = datos["correo"]

    puesto_txt = f" ({datos['lider_puesto']})" if datos["lider_puesto"] else ""
    empresa_txt = datos["nombre_empresa"] or "No especificada"

    cuerpo = f"""Se recibió un nuevo Brief de Diseño (Edición Personalizada).

Proyecto: {datos['nombre_proyecto']}
Contacto responsable: {datos['lider_nombre']}{puesto_txt}
Celular: {datos['celular']}
Correo: {datos['correo']}
Empresa: {empresa_txt}

El archivo ZIP adjunto contiene el brief completo en PDF y todos los archivos originales proporcionados por el cliente.

Este correo se generó automáticamente desde el formulario del brief."""
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
                to_addrs=destinatarios + bcc,
            )

        return True, (
            "✅ Tu brief y sus archivos se enviaron correctamente "
            "al equipo de Marketing."
        )
    except Exception as error:
        return False, (
            f"No se pudo enviar el correo automáticamente "
            f"({type(error).__name__}: {error}). "
            "Descarga el paquete ZIP y compártelo manualmente con Marketing."
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
            "por correo.</b><br/>Descarga el ZIP y compártelo manualmente con Marketing."
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
    with st.expander("🎨 <b> Conoce algunos ejemplos.</b>", expanded=True):
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
                    st.markdown(f"**{item['titulo']}**")
                    if item.get("desc"):
                        st.caption(item["desc"])


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
            "Correo *",
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
        lider_puesto = st.text_input(
            "Puesto",
            placeholder="Opcional — Ej. Gerente Comercial",
            key=f"lider_puesto_{_gen}",
        )

    col7, col8 = st.columns(2)
    with col7:
        pagina_web = st.text_input(
            "Página web",
            placeholder="https://tuempresa.com",
            key=f"pagina_web_{_gen}",
        )
    with col8:
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
# Características del diseño
# =========================================================
section_header("🎨 Características del diseño")

with st.container(border=True):
    objetivo_diseno = st.text_area(
        "Objetivo del diseño / Mensaje a comunicar (¿Qué debe transmitir el diseño? Cuéntanos sobre tu marca, a quién le hablas y qué quieres lograr con este producto.)*",
        placeholder="Mensaje abierto",
        height=120, key=f"objetivo_diseno_{_gen}")


    col3, col4 = st.columns(2)
    with col3:
        frase_eslogan = st.text_input("Frase o eslogan",
            placeholder="Opcional", key=f"frase_eslogan_{_gen}")
    with col4:
        paleta_colores = st.text_input(
            "Colores sugeridos",
            placeholder="Opcional — Ej. negro, gris, plata, dorado, azul, rojo, etc.",
            key=f"paleta_colores_{_gen}"
        )

    estilo_sel = st.selectbox("Estilo deseado *", ESTILOS_SUGERIDOS,
        key=f"estilo_sel_{_gen}", format_func=formato_opcion_estilo, index=None,
        placeholder="Selecciona una opción")
    estilo_otro = ""
    if estilo_sel == "Otro (especifica)":
        estilo_otro = st.text_input("Especifica el estilo deseado *",
            placeholder="Ej. Vintage, industrial, playero, etc.", key=f"estilo_otro_{_gen}")
    estilo_deseado = estilo_otro.strip() if estilo_sel == "Otro (especifica)" else (estilo_sel or "")

    iconografia = st.text_area(
        "Iconografía o símbolos relevantes",
        placeholder="Ej. logro, escudo, protección, finanzas, dinero, acompañamiento, asesoría...",
        height=80,
        key=f"iconografia_{_gen}"
    )


    elementos_graficos = st.text_area(
        "Elementos gráficos a incluir *",
        placeholder="Describe todo lo que deseas que aparezca en el diseño: nombre comercial, "
                    "palabras clave, fechas, frases, ilustraciones, símbolos u otros elementos.",
        height=110,
        key=f"elementos_graficos_{_gen}"
    )

    herramientas_notas = st.text_area(
        "Herramientas / referencias visuales (notas o links)",
        placeholder="Opcional — describe o pega links de moodboards, manuales de marca, Pinterest, etc.",
        height=80, key=f"herramientas_notas_{_gen}")
 

    informacion_adicional = st.text_area(
        "Notas / comentarios",
        placeholder="Opcional — agrega aquí cualquier nota, comentario o indicación que consideres relevante a considerar.",
        height=100,
        key=f"informacion_adicional_{_gen}"
    )

    st.markdown("**📎 Archivos de referencia**")

    st.caption(
        "Adjunta aquí cualquier material que pueda ayudarnos a entender mejor tu idea: "
        "imágenes, fotografías, ilustraciones, manuales de marca, PDFs, referencias visuales, etc."
    )

    adjuntos_files = st.file_uploader(
        "Adjuntar archivos (opcional)",
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
        background:#F2F2F2;
        border-left:4px solid #555555;
        padding:12px 16px;
        border-radius:6px;
        margin-top:18px;
        margin-bottom:18px;
        font-size:0.86rem;
        color:#444444;
    ">
        <b>Nota:</b> Los colores y acabados visualizados en pantalla son de carácter
        referencial y pueden presentar variaciones respecto al resultado final
        una vez impresos sobre la botella.
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Aceptación y envío
# =========================================================
section_header("✅ Confirmación y envío")

with st.container(border=True):
    copia_cliente = st.checkbox("Quiero recibir una copia de este brief en mi correo",
        key=f"copia_cliente_{_gen}")
    acepto = st.checkbox(
        "Confirmo que la información proporcionada es correcta y autorizo a Círculo Tequila "
        "a usarla para el diseño solicitado. *",
        key=f"acepto_{_gen}")

# Validaciones
errores = []
campos_requeridos = {
    "Nombre del proyecto": nombre_proyecto,
    "Contacto responsable del proyecto": lider_nombre,
    "Celular": celular,
    "Objetivo del diseño / Mensaje a comunicar": objetivo_diseno,
    "Elementos gráficos a incluir": elementos_graficos,
}
for etiqueta, valor in campos_requeridos.items():
    if not valor.strip():
        errores.append(f"• {etiqueta}")

if not correo.strip():
    errores.append("• Correo")
elif not es_correo_valido(correo):
    errores.append("• Correo (formato no válido)")

if not estilo_deseado.strip():
    errores.append("• Estilo deseado")

if not presentacion_375 and not presentacion_750:
    errores.append("• Selecciona al menos una presentación: 375 ml o 750 ml")

if peso_total_excedido:
    errores.append(
        f"• Los archivos adjuntos superan el límite total de "
        f"{TAMANO_MAX_ADJUNTOS_MB} MB"
    )

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
        "presentacion_375": bool(presentacion_375),
        "presentacion_750": bool(presentacion_750),
        "objetivo_diseno": objetivo_diseno.strip(),
        "frase_eslogan": frase_eslogan.strip(),
        "paleta_colores": paleta_colores.strip(),
        "estilo_deseado": estilo_deseado.strip(),
        "iconografia": iconografia.strip(),
        "elementos_graficos": elementos_graficos.strip(),
        "herramientas_notas": herramientas_notas.strip(),
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
            "Generando el PDF, preparando los archivos y enviándolos a Marketing..."
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
                copia_cliente,
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