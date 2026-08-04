import io
import zipfile
import smtplib
import mimetypes
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path

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
    KeepTogether,
    CondPageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas


# =========================================================
# Config + Branding (mismo estilo que Solicitud de Producción)
# =========================================================
PRIMARY = "#0F3D8A"
PRIMARY_DARK = "#0A2E66"
ACCENT_BG = "#EFF4FB"
GREY_LIGHT = "#F7F7F7"
GREY_BORDER = "#E5E5E5"
TEXT_DARK = "#1A1A1A"

st.set_page_config(
    page_title="Brief de Diseño · Círculo Tequila",
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
        box-shadow: 0 2px 10px rgba(15,61,138,0.18);
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

TAMANO_MAX_ADJUNTOS_MB = 20  # aviso si los adjuntos pesan más que esto


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
EJEMPLOS_INFO = [
    ("ejemplo_1_theralis.png", "Edición Empresarial",
     "Diseño institucional/arquitectónico para un cliente corporativo."),
    ("ejemplo_2_boda_myr.png", "Edición Personalizada",
     "Boda — estilo artístico e ilustrado, con iniciales y fecha."),
    ("ejemplo_3_20_aniversario.png", "Edición Conmemorativa",
     "20° Aniversario — estilo gráfico y moderno."),
    ("ejemplo_4_luna_llena.png", "Edición Artística",
     "Ilustración original de autor, estilo mexicano contemporáneo."),
    ("ejemplo_5_diagrama_impresion.png", "¿Cómo se ve al final?",
     "La impresión cubre tanto la cara frontal como la trasera de la botella."),
]


def get_ejemplos_disponibles() -> list:
    base = Path(__file__).resolve().parent / "assets" / "ejemplos"
    disponibles = []
    for fname, titulo, desc in EJEMPLOS_INFO:
        fpath = base / fname
        if fpath.exists():
            disponibles.append((fpath, titulo, desc))
    if disponibles:
        return disponibles

    # Respaldo: si los nombres de archivo no coinciden exactamente (por
    # ejemplo, algunas herramientas de subida de archivos truncan los
    # nombres a formato "8.3" tipo EJEMPL~1.PNG), se muestra de todas
    # formas cualquier imagen que exista en la carpeta, con un título
    # genérico, en vez de dejar la galería vacía.
    if base.exists():
        extensiones = (".png", ".jpg", ".jpeg", ".webp")
        for i, fpath in enumerate(sorted(base.iterdir()), start=1):
            if fpath.is_file() and fpath.suffix.lower() in extensiones:
                disponibles.append((fpath, f"Ejemplo {i}", ""))
    return disponibles


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
        <span>BRIEF DE DISEÑO · EDICIÓN EMPRESARIAL</span>
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
        emp_txt = self.empresa if len(self.empresa) <= 36 else self.empresa[:33] + "..."
        proy_txt = self.proyecto if len(self.proyecto) <= 36 else self.proyecto[:33] + "..."
        footer_y = 0.75 * cm
        self.drawString(1.3 * cm, footer_y, f"Empresa: {emp_txt}")
        self.drawCentredString(width / 2, footer_y, f"Proyecto: {proy_txt}")
        self.drawRightString(width - 1.3 * cm, footer_y, f"Pág. {page_num} / {total_pages}")
        self.setFont("Helvetica-Oblique", 7)
        self.setFillColor(PDF_MUTED)
        self.drawCentredString(width / 2, 0.40 * cm,
            "Círculo Tequila · Marketing — Brief de Diseño (Edición Empresarial)")


def _P(txt, style):
    return Paragraph(txt if txt else "—", style)


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
        return Paragraph(f"<b>{txt if txt else '—'}</b>", value_style)

    def title_banner():
        t = Table([[Paragraph("BRIEF DE DISEÑO", title_style)],
                   [Paragraph("Edición Empresarial · Círculo Tequila", subtitle_style)]],
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
        """archivos: lista de dicts {"nombre":..., "bytes":...} solo imágenes."""
        imgs = [a for a in archivos if es_imagen(a["nombre"])]
        no_imgs = [a for a in archivos if not es_imagen(a["nombre"])]
        flowables = []
        if not archivos:
            return flowables
        cap_tbl = Table([[Paragraph(f"ADJUNTOS — {titulo} ({len(archivos)})", img_caption_style)]],
                         colWidths=[18.4 * cm])
        cap_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PDF_RED_DARK),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        flowables.append(Spacer(1, 0.15 * cm))
        flowables.append(cap_tbl)
        max_w, max_h = 16.0 * cm, 9.0 * cm
        for a in imgs:
            try:
                rl_img = RLImage(io.BytesIO(a["bytes"]))
                ratio = rl_img.imageWidth / rl_img.imageHeight
                if ratio > (max_w / max_h):
                    rl_img.drawWidth = max_w
                    rl_img.drawHeight = max_w / ratio
                else:
                    rl_img.drawHeight = max_h
                    rl_img.drawWidth = max_h * ratio
                img_wrap = Table([[rl_img]], colWidths=[18.4 * cm])
                img_wrap.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("BOX", (0, 0), (-1, -1), 0.5, PDF_GREY_BORDER),
                    ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]))
                flowables.append(img_wrap)
                flowables.append(Spacer(1, 0.10 * cm))
            except Exception:
                no_imgs.append(a)
        if no_imgs:
            nombres = ", ".join(a["nombre"] for a in no_imgs)
            flowables.append(Paragraph(
                f"<i>Otros archivos adjuntos en esta sección (incluidos en el .zip por correo): {nombres}</i>",
                body_style))
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
        Paragraph(f"<font size=11><b>{datos['fecha']}</b></font>", label_style),
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
        [L("Empresa"), V(datos["nombre_empresa"]), L("Proyecto"), V(datos["nombre_proyecto"])],
        [L("Página web"), V(datos["pagina_web"]), L("Redes sociales"), V(datos["redes_sociales"])],
        [L("Líder de proyecto"), V(datos["lider_nombre"]), L("Puesto"), V(datos["lider_puesto"])],
        [L("Celular"), V(datos["celular"]), L("Correo"), V(datos["correo"])],
    ]))

    story.append(Spacer(1, 0.30 * cm))
    story.append(section_band("VOLUMEN DE PRODUCCIÓN"))
    story.append(Spacer(1, 0.15 * cm))
    story.append(kv4_table([
        [L("375 ml — Cantidad"), V(datos["cantidad_375"]), L("750 ml — Cantidad"), V(datos["cantidad_750"])],
    ]))

    story.append(Spacer(1, 0.30 * cm))
    story.append(section_band("CARACTERÍSTICAS DEL DISEÑO"))
    story.append(Spacer(1, 0.15 * cm))
    story.append(texto_bloque("Objetivo del diseño / Mensaje a comunicar", datos["objetivo_diseno"]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(kv4_table([
        [L("Frase o eslogan"), V(datos["frase_eslogan"]), L("Estilo deseado"), V(datos["estilo_deseado"])],
        [L("Paleta de colores"), V(datos["paleta_colores"]), L("Logo"),
         V("Adjunto en esta solicitud" if datos["tiene_logo"] else "Diseñar desde cero (sin logo previo)")],
    ]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(texto_bloque("Iconografía o símbolos relevantes", datos["iconografia"]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(texto_bloque("Elementos gráficos a incluir", datos["elementos_graficos"]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(texto_bloque("Herramientas / referencias visuales (notas)", datos["herramientas_notas"]))
    story.append(Spacer(1, 0.12 * cm))
    story.append(texto_bloque("Información adicional", datos["informacion_adicional"]))
    if datos.get("link_archivos_pesados"):
        story.append(Spacer(1, 0.12 * cm))
        story.append(texto_bloque("Link a archivos pesados (WeTransfer / Drive / otro)",
                                   datos["link_archivos_pesados"]))

    for titulo, archivos in adjuntos_por_seccion.items():
        story.extend(imagenes_seccion(titulo, archivos))

    story.append(Spacer(1, 0.3 * cm))
    aceptacion = Table([[Paragraph(
        f"<i>Brief confirmado digitalmente por <b>{datos['lider_nombre']}</b> "
        f"({datos['correo']}) el {datos['fecha']}. El material gráfico adjunto "
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
def build_zip_bytes(adjuntos_por_seccion: dict) -> bytes | None:
    total_archivos = sum(len(v) for v in adjuntos_por_seccion.values())
    if total_archivos == 0:
        return None
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for carpeta, archivos in adjuntos_por_seccion.items():
            for a in archivos:
                zf.writestr(f"{carpeta}/{a['nombre']}", a["bytes"])
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


def enviar_correo(datos, pdf_bytes, zip_bytes, copia_cliente: bool) -> tuple[bool, str]:
    cfg = get_smtp_config()
    if cfg is None:
        return False, (
            "El envío automático de correo aún no está configurado en esta app "
            "(faltan los 'secrets' de SMTP). Descarga el PDF y el .zip de abajo "
            "y compártelos manualmente con marketing mientras se configura."
        )

    destinatarios = [d.strip() for d in cfg["to_email"].split(",") if d.strip()]
    bcc = [datos["correo"]] if copia_cliente and es_correo_valido(datos["correo"]) else []

    msg = EmailMessage()
    msg["Subject"] = f"Brief de Diseño · {datos['nombre_empresa']} — {datos['nombre_proyecto']}"
    msg["From"] = f"{cfg['from_name']} <{cfg['user']}>"
    msg["To"] = ", ".join(destinatarios)
    msg["Reply-To"] = datos["correo"]
    cuerpo = (
        f"Se recibió un nuevo Brief de Diseño (Edición Empresarial).\n\n"
        f"Empresa: {datos['nombre_empresa']}\n"
        f"Proyecto: {datos['nombre_proyecto']}\n"
        f"Líder de proyecto: {datos['lider_nombre']} ({datos['lider_puesto']})\n"
        f"Celular: {datos['celular']}\n"
        f"Correo: {datos['correo']}\n\n"
        f"Se adjunta el brief en PDF"
        + (" y un .zip con el material gráfico proporcionado." if zip_bytes else ".")
        + "\n\nEste correo se generó automáticamente desde el link de llenado del brief."
    )
    msg.set_content(cuerpo)

    nombre_base = f"{datos['nombre_empresa']}_{datos['nombre_proyecto']}".strip("_ ").replace(" ", "_") or "brief"
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf",
                        filename=f"Brief_{nombre_base}.pdf")
    if zip_bytes:
        msg.add_attachment(zip_bytes, maintype="application", subtype="zip",
                            filename=f"Adjuntos_{nombre_base}.zip")

    todos_destinatarios = destinatarios + bcc
    try:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30) as server:
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg, to_addrs=todos_destinatarios)
        return True, "✅ Tu brief se envió correctamente al equipo de marketing."
    except Exception as e:
        return False, (
            f"No se pudo enviar el correo automáticamente ({e}). "
            "Descarga el PDF y el .zip de abajo y compártelos manualmente con marketing."
        )


# =========================================================
# Pantalla de éxito (después de enviar)
# =========================================================
if st.session_state.submitted:
    res = st.session_state.submit_result
    if res.get("email_ok"):
        st.success(res.get("email_msg", "✅ Brief enviado correctamente."))
    else:
        st.warning(res.get("email_msg", "No se pudo enviar el correo automáticamente."))

    st.markdown(
        f"""
        <div class="intro-card">
            <b>¡Gracias, {res.get('lider_nombre','')}! 🎉</b><br/>
            Recibimos el brief de <b>{res.get('nombre_empresa','')}</b> para el proyecto
            <b>{res.get('nombre_proyecto','')}</b>. El equipo de diseño de Círculo Tequila
            lo revisará y se pondrá en contacto contigo a la brevedad.
        </div>
        """,
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
        if res.get("zip_bytes"):
            st.download_button(
                "⬇️ Descargar adjuntos (.zip)",
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
        👋 <b>¡Hola! Este formulario nos ayuda a entender exactamente qué necesitas
        para tu diseño.</b><br/>
        Tómate unos minutos para llenarlo con el mayor detalle posible — entre más
        clara sea la información, más rápido y preciso será el resultado. Los campos
        marcados con <b>*</b> son obligatorios. Puedes adjuntar tu logo e imágenes de
        referencia directamente aquí, no necesitas usar WeTransfer por separado.
    </div>
    """,
    unsafe_allow_html=True,
)

ejemplos_disponibles = get_ejemplos_disponibles()
if ejemplos_disponibles:
    with st.expander("🎨 Inspírate: ejemplos de lo que puedes lograr", expanded=True):
        st.caption(
            "Estos son algunos diseños que ya creamos para otros clientes — solo para "
            "darte una idea de las posibilidades antes de describir el tuyo."
        )
        cols_ej = st.columns(3)
        for i, (fpath, titulo, desc) in enumerate(ejemplos_disponibles):
            with cols_ej[i % 3]:
                st.image(str(fpath), use_container_width=True)
                st.markdown(f"**{titulo}**")
                if desc:
                    st.caption(desc)

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
        "• Logotipos: si los tienes, en formato vectorial (.ai) es ideal.\n\n"
        "• Fotos/imágenes: en alta resolución (300 dpi) si es posible.\n\n"
        "• Si tus archivos pesan mucho, agrégalos igual — o dejamos un link de "
        "WeTransfer/Drive como respaldo al final del formulario."
    )
    st.markdown("---")
    st.caption(f"📅 {fecha_es(datetime.now())}")


# =========================================================
# Datos Cliente / Empresa
# =========================================================
section_header("🏢 Datos Cliente / Empresa")

with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        nombre_empresa = st.text_input("Nombre de la empresa *",
            placeholder="Ej. G&NC Asesores Patrimoniales", key=f"nombre_empresa_{_gen}")
        pagina_web = st.text_input("Página web",
            placeholder="https://tuempresa.com", key=f"pagina_web_{_gen}")
        lider_nombre = st.text_input("Nombre líder del proyecto *",
            placeholder="Nombre completo", key=f"lider_nombre_{_gen}")
        celular = st.text_input("Celular *",
            placeholder="Ej. 33 1234 5678", key=f"celular_{_gen}")
    with col2:
        nombre_proyecto = st.text_input("Nombre del proyecto *",
            placeholder="Ej. Lanzamiento línea corporativa", key=f"nombre_proyecto_{_gen}")
        redes_sociales = st.text_input("Redes sociales",
            placeholder="@tuempresa", key=f"redes_sociales_{_gen}")
        lider_puesto = st.text_input("Puesto *",
            placeholder="Ej. Gerente Comercial", key=f"lider_puesto_{_gen}")
        correo = st.text_input("Correo *",
            placeholder="nombre@empresa.com", key=f"correo_{_gen}")


# =========================================================
# Volumen de producción
# =========================================================
section_header("🍶 Volumen de producción", "Opcional — si ya tienes una cantidad estimada")

with st.container(border=True):
    colv1, colv2 = st.columns(2)
    with colv1:
        cantidad_375 = st.number_input("375 ml — Cantidad", min_value=0, step=1, value=0,
            key=f"cantidad_375_{_gen}")
    with colv2:
        cantidad_750 = st.number_input("750 ml — Cantidad", min_value=0, step=1, value=0,
            key=f"cantidad_750_{_gen}")


# =========================================================
# Características del diseño
# =========================================================
section_header("🎨 Características del diseño")

with st.container(border=True):
    objetivo_diseno = st.text_area(
        "Objetivo del diseño / Mensaje a comunicar *",
        placeholder="¿Qué debe transmitir el diseño? Cuéntanos sobre tu marca, a quién le hablas y qué "
                    "quieres lograr con este producto.",
        height=120, key=f"objetivo_diseno_{_gen}")

    st.markdown("**Logo de empresa (adjuntar) ***")
    sin_logo = st.checkbox("No tengo logo — que Círculo Tequila lo diseñe", key=f"sin_logo_{_gen}")
    logo_files = st.file_uploader(
        "Sube tu logo (idealmente en formato vectorial .ai, o imagen en alta resolución)",
        type=None, accept_multiple_files=True, key=f"logo_files_{_gen}",
        disabled=sin_logo,
    )
    if logo_files:
        cols_logo = st.columns(min(len(logo_files), 3))
        for fi, f in enumerate(logo_files):
            with cols_logo[fi % 3]:
                if es_imagen(f.name):
                    st.image(f.getvalue(), caption=f.name, use_container_width=True)
                else:
                    st.info(f"📎 {f.name}")

    col3, col4 = st.columns(2)
    with col3:
        frase_eslogan = st.text_input("Frase o eslogan",
            placeholder="Opcional", key=f"frase_eslogan_{_gen}")
    with col4:
        paleta_colores = st.text_input("Paleta de colores sugerida *",
            placeholder="Ej. Colores del logotipo — tintos/rojos y negros",
            key=f"paleta_colores_{_gen}")

    estilo_sel = st.selectbox("Estilo deseado *", ESTILOS_SUGERIDOS,
        key=f"estilo_sel_{_gen}", format_func=formato_opcion_estilo, index=None,
        placeholder="Selecciona una opción")
    estilo_otro = ""
    if estilo_sel == "Otro (especifica)":
        estilo_otro = st.text_input("Especifica el estilo deseado *",
            placeholder="Ej. Vintage, industrial, playero, etc.", key=f"estilo_otro_{_gen}")
    estilo_deseado = estilo_otro.strip() if estilo_sel == "Otro (especifica)" else (estilo_sel or "")

    iconografia = st.text_area("Iconografía o símbolos relevantes",
        placeholder="Ej. logro, escudo, protección, finanzas, dinero, acompañamiento, asesoría...",
        height=80, key=f"iconografia_{_gen}")
    iconografia_files = st.file_uploader(
        "Adjuntar referencias de iconografía (opcional)",
        type=None, accept_multiple_files=True, key=f"iconografia_files_{_gen}")
    if iconografia_files:
        cols_icon = st.columns(min(len(iconografia_files), 3))
        for fi, f in enumerate(iconografia_files):
            with cols_icon[fi % 3]:
                if es_imagen(f.name):
                    st.image(f.getvalue(), caption=f.name, use_container_width=True)
                else:
                    st.info(f"📎 {f.name}")

    elementos_graficos = st.text_area(
        "Elementos gráficos a incluir *",
        placeholder="Describe todo lo que se desea que aparezca en el diseño: logotipo, nombre "
                    "comercial, palabras clave, dónde se entregarán las botellas, etc.",
        height=110, key=f"elementos_graficos_{_gen}")

    herramientas_notas = st.text_area(
        "Herramientas / referencias visuales (notas o links)",
        placeholder="Opcional — describe o pega links de moodboards, manuales de marca, Pinterest, etc.",
        height=80, key=f"herramientas_notas_{_gen}")
    herramientas_files = st.file_uploader(
        "Adjuntar imágenes, moodboard o manuales de referencia (opcional)",
        type=None, accept_multiple_files=True, key=f"herramientas_files_{_gen}")
    if herramientas_files:
        cols_h = st.columns(min(len(herramientas_files), 3))
        for fi, f in enumerate(herramientas_files):
            with cols_h[fi % 3]:
                if es_imagen(f.name):
                    st.image(f.getvalue(), caption=f.name, use_container_width=True)
                else:
                    st.info(f"📎 {f.name}")

    informacion_adicional = st.text_area(
        "Información adicional *",
        placeholder="Instrucciones especiales, datos del domicilio y contacto de la persona para "
                    "entrega, fechas importantes, etc.",
        height=100, key=f"informacion_adicional_{_gen}")

    link_archivos_pesados = st.text_input(
        "Link a archivos pesados (opcional — WeTransfer, Drive, etc.)",
        placeholder="Si tus archivos son muy grandes, pega aquí el link como respaldo",
        key=f"link_pesados_{_gen}")


# =========================================================
# Validación de tamaño de adjuntos
# =========================================================
todos_los_archivos = list(logo_files or []) + list(iconografia_files or []) + list(herramientas_files or [])
peso_total = sum(len(f.getvalue()) for f in todos_los_archivos)
if peso_total > TAMANO_MAX_ADJUNTOS_MB * 1024 * 1024:
    st.warning(
        f"⚠️ Tus archivos adjuntos pesan {tam_legible(peso_total)} en total. Podrían no llegar "
        f"completos por correo. Te recomendamos también dejar un link de WeTransfer/Drive arriba "
        f"como respaldo."
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
    "Nombre de la empresa": nombre_empresa,
    "Nombre del proyecto": nombre_proyecto,
    "Nombre líder del proyecto": lider_nombre,
    "Puesto": lider_puesto,
    "Celular": celular,
    "Objetivo del diseño / Mensaje a comunicar": objetivo_diseno,
    "Paleta de colores sugerida": paleta_colores,
    "Elementos gráficos a incluir": elementos_graficos,
    "Información adicional": informacion_adicional,
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

if not sin_logo and not logo_files:
    errores.append("• Logo de empresa (adjunta un archivo o marca \"No tengo logo\")")

if not acepto:
    errores.append("• Debes confirmar la casilla de aceptación")

puede_enviar = len(errores) == 0

if errores:
    st.warning("⚠️ Antes de enviar, revisa lo siguiente:\n\n" + "\n".join(errores))

if st.button("📩 Enviar brief", type="primary", disabled=not puede_enviar, use_container_width=True):
    datos = {
        "fecha": fecha_es(datetime.now()),
        "nombre_empresa": nombre_empresa.strip(),
        "nombre_proyecto": nombre_proyecto.strip(),
        "pagina_web": pagina_web.strip(),
        "redes_sociales": redes_sociales.strip(),
        "lider_nombre": lider_nombre.strip(),
        "lider_puesto": lider_puesto.strip(),
        "celular": celular.strip(),
        "correo": correo.strip(),
        "cantidad_375": str(int(cantidad_375)),
        "cantidad_750": str(int(cantidad_750)),
        "objetivo_diseno": objetivo_diseno.strip(),
        "tiene_logo": bool(logo_files),
        "frase_eslogan": frase_eslogan.strip(),
        "paleta_colores": paleta_colores.strip(),
        "estilo_deseado": estilo_deseado.strip(),
        "iconografia": iconografia.strip(),
        "elementos_graficos": elementos_graficos.strip(),
        "herramientas_notas": herramientas_notas.strip(),
        "informacion_adicional": informacion_adicional.strip(),
        "link_archivos_pesados": link_archivos_pesados.strip(),
    }

    adjuntos_por_seccion = {
        "Logo": [{"nombre": f.name, "bytes": f.getvalue()} for f in (logo_files or [])],
        "Iconografia": [{"nombre": f.name, "bytes": f.getvalue()} for f in (iconografia_files or [])],
        "Referencias": [{"nombre": f.name, "bytes": f.getvalue()} for f in (herramientas_files or [])],
    }

    with st.spinner("Generando tu brief y enviándolo a marketing..."):
        pdf_bytes = build_brief_pdf(datos, adjuntos_por_seccion)
        zip_bytes = build_zip_bytes(adjuntos_por_seccion)
        email_ok, email_msg = enviar_correo(datos, pdf_bytes, zip_bytes, copia_cliente)

    nombre_base = f"{datos['nombre_empresa']}_{datos['nombre_proyecto']}".strip("_ ").replace(" ", "_") or "brief"
    st.session_state.submit_result = {
        "email_ok": email_ok,
        "email_msg": email_msg,
        "pdf_bytes": pdf_bytes,
        "pdf_name": f"Brief_{nombre_base}.pdf",
        "zip_bytes": zip_bytes,
        "zip_name": f"Adjuntos_{nombre_base}.zip",
        "lider_nombre": datos["lider_nombre"],
        "nombre_empresa": datos["nombre_empresa"],
        "nombre_proyecto": datos["nombre_proyecto"],
    }
    st.session_state.submitted = True
    st.rerun()