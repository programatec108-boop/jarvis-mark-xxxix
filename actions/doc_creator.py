# doc_creator.py - Creador de documentos Word y PDF para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\doc_creator.py
# Requiere: pip install python-docx reportlab requests pillow

import json
import time
import requests
import io
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DESKTOP  = Path("C:\\Users\\jose1\\Desktop")

# Importar helper de Gemini
import sys
sys.path.insert(0, str(BASE_DIR / "actions"))
from gemini_helper import ask_gemini_json


def _descargar_imagen(query, ancho=400, alto=250):
    """Descarga imagen de Pixabay (gratis, sin API key)."""
    try:
        search = query.replace(" ", "+")
        api_url = f"https://pixabay.com/api/?key=55880202-0527210ccd1217ec239e9b65d&q={search}&image_type=photo&per_page=3&safesearch=true"
        r = requests.get(api_url, timeout=10)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            if hits:
                img_url = hits[0].get("webformatURL", "")
                if img_url:
                    img_r = requests.get(img_url, timeout=15)
                    if img_r.status_code == 200 and len(img_r.content) > 1000:
                        return io.BytesIO(img_r.content)
    except Exception as e:
        print("[DocCreator] Imagen error: " + str(e))
    return None



def _investigar_tema(tema, paginas=4):
    prompt = f"""Eres un redactor academico experto. Crea un documento completo sobre: "{tema}"

Responde SOLO JSON valido:
{{
  "titulo": "Titulo del documento",
  "subtitulo": "Subtitulo descriptivo",
  "autor": "Jose Antonio Carbajal Quintanar",
  "fecha": "{datetime.now().strftime('%d de %B de %Y')}",
  "resumen": "Parrafo de resumen ejecutivo de 3-4 oraciones.",
  "usar_imagenes": true,
  "secciones": [
    {{
      "titulo": "1. Introduccion",
      "contenido": "Parrafo completo con minimo 150 palabras. Formal y academico.",
      "subsecciones": [
        {{
          "titulo": "1.1 Subtema",
          "contenido": "Contenido de subseccion con minimo 80 palabras."
        }}
      ],
      "imagen_buscar": "keyword in english"
    }}
  ],
  "conclusion": "Parrafo de conclusion con minimo 80 palabras.",
  "referencias": [
    "Autor, A. (2023). Titulo. Editorial.",
    "Sitio Web (2024). Titulo. https://ejemplo.com"
  ]
}}

Reglas:
- Minimo {paginas} secciones principales bien desarrolladas
- Contenido academico formal en espanol
- usar_imagenes: true si el tema se beneficia de imagenes, false si es abstracto
- imagen_buscar: 2-3 palabras en ingles
- Cada seccion con minimo 150 palabras"""

    return ask_gemini_json(prompt)


def _crear_word(contenido, nombre_archivo):
    try:
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc     = Document()
        section = doc.sections[0]
        section.top_margin    = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin   = Cm(3)
        section.right_margin  = Cm(2.5)

        # Portada
        doc.add_paragraph()
        doc.add_paragraph()
        titulo_p = doc.add_paragraph()
        titulo_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = titulo_p.add_run(contenido.get("titulo", "Documento"))
        run.bold = True
        run.font.size = Pt(24)
        run.font.color.rgb = RGBColor(0x1a, 0x1a, 0x5e)
        doc.add_paragraph()

        if contenido.get("subtitulo"):
            sub_p = doc.add_paragraph()
            sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run2 = sub_p.add_run(contenido["subtitulo"])
            run2.font.size = Pt(14)
            run2.font.color.rgb = RGBColor(0x44, 0x44, 0x88)

        doc.add_paragraph()
        doc.add_paragraph()
        info_p = doc.add_paragraph()
        info_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = info_p.add_run(f"Autor: {contenido.get('autor', 'Jose Antonio Carbajal')}\n")
        r1.bold = True
        info_p.add_run(f"Fecha: {contenido.get('fecha', datetime.now().strftime('%d/%m/%Y'))}")
        doc.add_page_break()

        # Resumen
        if contenido.get("resumen"):
            h = doc.add_heading("Resumen Ejecutivo", level=1)
            h.runs[0].font.color.rgb = RGBColor(0x1a, 0x1a, 0x5e)
            doc.add_paragraph(contenido["resumen"])
            doc.add_paragraph()

        # Secciones
        usar_imagenes = contenido.get("usar_imagenes", False)
        for seccion in contenido.get("secciones", []):
            h = doc.add_heading(seccion.get("titulo", "Seccion"), level=1)
            h.runs[0].font.color.rgb = RGBColor(0x1a, 0x1a, 0x5e)
            if seccion.get("contenido"):
                doc.add_paragraph(seccion["contenido"])

            if usar_imagenes and seccion.get("imagen_buscar"):
                img_data = _descargar_imagen(seccion["imagen_buscar"])
                if img_data:
                    try:
                        p_img = doc.add_paragraph()
                        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        p_img.add_run().add_picture(img_data, width=Inches(4.5))
                        cap = doc.add_paragraph(f"Figura: {seccion['imagen_buscar'].title()}")
                        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        cap.runs[0].italic = True
                        cap.runs[0].font.size = Pt(9)
                    except Exception:
                        pass

            for sub in seccion.get("subsecciones", []):
                h2 = doc.add_heading(sub.get("titulo", ""), level=2)
                h2.runs[0].font.color.rgb = RGBColor(0x33, 0x33, 0x99)
                doc.add_paragraph(sub.get("contenido", ""))
            doc.add_paragraph()

        # Conclusion
        if contenido.get("conclusion"):
            h = doc.add_heading("Conclusión", level=1)
            h.runs[0].font.color.rgb = RGBColor(0x1a, 0x1a, 0x5e)
            doc.add_paragraph(contenido["conclusion"])
            doc.add_paragraph()

        # Referencias
        if contenido.get("referencias"):
            h = doc.add_heading("Referencias", level=1)
            h.runs[0].font.color.rgb = RGBColor(0x1a, 0x1a, 0x5e)
            for ref in contenido["referencias"]:
                doc.add_paragraph(ref, style="List Bullet")

        ruta = DESKTOP / (nombre_archivo + ".docx")
        doc.save(str(ruta))
        return str(ruta)

    except Exception as e:
        print("[DocCreator] Word error: " + str(e))
        import traceback
        traceback.print_exc()
        return None


def _crear_pdf(contenido, nombre_archivo):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            HRFlowable, PageBreak, Image as RLImage
        )
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

        ruta = DESKTOP / (nombre_archivo + ".pdf")
        doc  = SimpleDocTemplate(
            str(ruta), pagesize=A4,
            rightMargin=2.5*cm, leftMargin=3*cm,
            topMargin=2.5*cm,   bottomMargin=2.5*cm,
        )

        COLOR_TITULO = colors.HexColor("#1a1a5e")
        COLOR_SUB    = colors.HexColor("#444488")
        estilos      = getSampleStyleSheet()

        estilo_titulo  = ParagraphStyle("TP", parent=estilos["Title"],
            fontSize=26, textColor=COLOR_TITULO, spaceAfter=12, alignment=TA_CENTER, leading=32)
        estilo_sub     = ParagraphStyle("SP", parent=estilos["Normal"],
            fontSize=14, textColor=COLOR_SUB, spaceAfter=8, alignment=TA_CENTER)
        estilo_autor   = ParagraphStyle("AP", parent=estilos["Normal"],
            fontSize=11, alignment=TA_CENTER, spaceAfter=4)
        estilo_h1      = ParagraphStyle("H1P", parent=estilos["Heading1"],
            fontSize=16, textColor=COLOR_TITULO, spaceBefore=16, spaceAfter=8, leading=20)
        estilo_h2      = ParagraphStyle("H2P", parent=estilos["Heading2"],
            fontSize=13, textColor=colors.HexColor("#333399"), spaceBefore=10, spaceAfter=6)
        estilo_cuerpo  = ParagraphStyle("CP", parent=estilos["Normal"],
            fontSize=11, leading=16, alignment=TA_JUSTIFY, spaceAfter=8)
        estilo_caption = ParagraphStyle("CAP", parent=estilos["Normal"],
            fontSize=9, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=8)
        estilo_ref     = ParagraphStyle("RP", parent=estilos["Normal"],
            fontSize=9, leftIndent=20, spaceAfter=4)

        historia = [
            Spacer(1, 3*cm),
            Paragraph(contenido.get("titulo", "Documento"), estilo_titulo),
            Spacer(1, 0.5*cm),
        ]
        if contenido.get("subtitulo"):
            historia.append(Paragraph(contenido["subtitulo"], estilo_sub))
        historia += [
            Spacer(1, 2*cm),
            HRFlowable(width="100%", thickness=2, color=COLOR_TITULO),
            Spacer(1, 0.5*cm),
            Paragraph(f"<b>Autor:</b> {contenido.get('autor', 'Jose Antonio Carbajal')}", estilo_autor),
            Paragraph(f"<b>Fecha:</b> {contenido.get('fecha', datetime.now().strftime('%d/%m/%Y'))}", estilo_autor),
            PageBreak(),
        ]

        if contenido.get("resumen"):
            historia += [
                Paragraph("Resumen Ejecutivo", estilo_h1),
                HRFlowable(width="100%", thickness=1, color=colors.lightgrey),
                Spacer(1, 0.3*cm),
                Paragraph(contenido["resumen"], estilo_cuerpo),
                Spacer(1, 0.5*cm),
            ]

        usar_imagenes = contenido.get("usar_imagenes", False)
        for seccion in contenido.get("secciones", []):
            historia += [
                Paragraph(seccion.get("titulo", ""), estilo_h1),
                HRFlowable(width="100%", thickness=1, color=colors.lightgrey),
                Spacer(1, 0.3*cm),
            ]
            if seccion.get("contenido"):
                historia.append(Paragraph(seccion["contenido"], estilo_cuerpo))

            if usar_imagenes and seccion.get("imagen_buscar"):
                img_data = _descargar_imagen(seccion["imagen_buscar"], 500, 300)
                if img_data:
                    try:
                        historia += [
                            Spacer(1, 0.3*cm),
                            RLImage(img_data, width=12*cm, height=7*cm),
                            Paragraph(f"<i>Figura: {seccion['imagen_buscar'].title()}</i>", estilo_caption),
                        ]
                    except Exception:
                        pass

            for sub in seccion.get("subsecciones", []):
                historia += [
                    Paragraph(sub.get("titulo", ""), estilo_h2),
                    Paragraph(sub.get("contenido", ""), estilo_cuerpo),
                ]
            historia.append(Spacer(1, 0.5*cm))

        if contenido.get("conclusion"):
            historia += [
                Paragraph("Conclusión", estilo_h1),
                HRFlowable(width="100%", thickness=1, color=colors.lightgrey),
                Spacer(1, 0.3*cm),
                Paragraph(contenido["conclusion"], estilo_cuerpo),
                Spacer(1, 0.5*cm),
            ]

        if contenido.get("referencias"):
            historia += [
                Paragraph("Referencias", estilo_h1),
                HRFlowable(width="100%", thickness=1, color=colors.lightgrey),
                Spacer(1, 0.3*cm),
            ]
            for ref in contenido["referencias"]:
                historia.append(Paragraph("• " + ref, estilo_ref))

        doc.build(historia)
        return str(ruta)

    except Exception as e:
        print("[DocCreator] PDF error: " + str(e))
        import traceback
        traceback.print_exc()
        return None


def doc_creator(parameters, player=None, speak=None):
    tema     = parameters.get("tema", parameters.get("topic", "")).strip()
    formato  = parameters.get("formato", "ambos").lower()
    paginas  = int(parameters.get("paginas", 4))
    imagenes = parameters.get("imagenes", "auto")

    if not tema:
        return "Dime el tema del documento, jefe."

    if speak:
        speak(f"Investigando '{tema}', jefe. Dame un momento.")
    if player:
        player.write_log(f"[DocCreator] Investigando: {tema}")

    contenido = _investigar_tema(tema, paginas)
    if not contenido:
        return f"No pude investigar '{tema}', jefe. Verifica tu conexion a internet."

    if imagenes == "true" or imagenes is True:
        contenido["usar_imagenes"] = True
    elif imagenes == "false" or imagenes is False:
        contenido["usar_imagenes"] = False

    if speak:
        speak("Investigacion completa, jefe. Generando el documento ahora.")
    if player:
        player.write_log(f"[DocCreator] {len(contenido.get('secciones', []))} secciones.")

    nombre = tema.replace(" ", "_").replace("/", "-")[:40]
    nombre = "".join(c for c in nombre if c.isalnum() or c in "_-")

    archivos_creados = []

    if formato in ("word", "ambos"):
        if player:
            player.write_log("[DocCreator] Creando Word...")
        ruta_word = _crear_word(contenido, nombre)
        if ruta_word:
            archivos_creados.append(ruta_word)

    if formato in ("pdf", "ambos"):
        if player:
            player.write_log("[DocCreator] Creando PDF...")
        ruta_pdf = _crear_pdf(contenido, nombre)
        if ruta_pdf:
            archivos_creados.append(ruta_pdf)

    if not archivos_creados:
        return "Jefe, tuve problemas creando el documento. Verifica que tenga instalado python-docx y reportlab."

    import subprocess
    for ruta in archivos_creados:
        try:
            subprocess.Popen(["explorer", ruta])
            time.sleep(1)
        except Exception:
            pass

    secciones = len(contenido.get("secciones", []))
    con_img   = "con imagenes" if contenido.get("usar_imagenes") else "sin imagenes"
    return (
        f"Listo, jefe. Documento sobre '{tema}' creado {con_img}: "
        f"{secciones} secciones, resumen, conclusion y referencias. "
        f"Lo guarde en su escritorio y lo abri automaticamente."
    )
