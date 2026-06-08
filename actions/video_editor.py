# video_editor.py - Editor de video para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\video_editor.py
# Requiere: pip install moviepy pillow

import os
import time
import subprocess
import random
from pathlib import Path

DESKTOP    = Path("C:\\Users\\jose1\\Desktop")
VIDEOS_DIR = Path("C:\\Users\\jose1\\Videos")
MUSICA_DIR = Path("C:\\Users\\jose1\\Music")

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v", ".ts"}
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".flac"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _encontrar_archivos(carpeta=None):
    """Encuentra videos E imágenes en una carpeta."""
    if carpeta:
        ruta = Path(carpeta)
    else:
        for lugar in [DESKTOP, VIDEOS_DIR, Path("C:\\Users\\jose1\\Downloads")]:
            if lugar.exists():
                archivos = [f for f in lugar.iterdir()
                           if f.suffix.lower() in VIDEO_EXTS | IMAGE_EXTS]
                if archivos:
                    return archivos, lugar
        return [], None

    if not ruta.exists():
        return [], None

    archivos = [f for f in ruta.iterdir()
                if f.suffix.lower() in VIDEO_EXTS | IMAGE_EXTS]
    return sorted(archivos), ruta


def _encontrar_musica(query=None):
    """Encuentra música para el video."""
    lugares = [MUSICA_DIR, DESKTOP, Path("C:\\Users\\jose1\\Downloads")]
    for lugar in lugares:
        if lugar.exists():
            for ext in AUDIO_EXTS:
                archivos = list(lugar.glob(f"*{ext}"))
                if archivos:
                    if query:
                        for a in archivos:
                            if query.lower() in a.name.lower():
                                return a
                    return random.choice(archivos)
    return None


def _hacer_slideshow(imagenes, output_path, musica=None, duracion_foto=3, player=None):
    """Crea un video slideshow a partir de imágenes."""
    try:
        from moviepy import ImageClip, concatenate_videoclips, AudioFileClip
        from moviepy import afx
        from PIL import Image as PILImage
        import numpy as np

        if player:
            player.write_log(f"[Video] Creando slideshow con {len(imagenes)} fotos...")

        # Determinar resolucion comun (la de la primera imagen valida)
        target_w, target_h = 1280, 720
        for img_path in imagenes[:3]:
            try:
                with PILImage.open(str(img_path)) as im:
                    w, h = im.size
                    # Detectar si es horizontal o vertical
                    if w > h:
                        target_w, target_h = 1280, 720
                    else:
                        target_w, target_h = 720, 1280
                break
            except Exception:
                continue

        clips = []
        for img in imagenes:
            try:
                # Redimensionar imagen para que todas sean del mismo tamano
                with PILImage.open(str(img)) as im:
                    im = im.convert("RGB")
                    # Fit dentro del target manteniendo aspecto
                    im.thumbnail((target_w, target_h), PILImage.LANCZOS)
                    # Crear fondo negro y pegar centrado
                    fondo = PILImage.new("RGB", (target_w, target_h), (0, 0, 0))
                    offset = ((target_w - im.width) // 2, (target_h - im.height) // 2)
                    fondo.paste(im, offset)
                    arr = np.array(fondo)

                clip = ImageClip(arr, duration=duracion_foto)
                clip = clip.with_fps(24)
                clips.append(clip)
                if player:
                    player.write_log(f"[Video] Foto {len(clips)}/{len(imagenes)}: {img.name}")
            except Exception as e:
                print(f"[Video] Error cargando imagen {img.name}: {e}")
                continue

        if not clips:
            return False, "No pude cargar las imágenes."

        video_final = concatenate_videoclips(clips, method="compose")

        # Agregar música si hay
        if musica and Path(musica).exists():
            try:
                audio = AudioFileClip(str(musica))
                if audio.duration > video_final.duration:
                    audio = audio.subclipped(0, video_final.duration)
                else:
                    audio = audio.with_effects([afx.AudioLoop(duration=video_final.duration)])
                audio = audio.with_effects([afx.MultiplyVolume(0.8)])
                video_final = video_final.with_audio(audio)
                if player:
                    player.write_log(f"[Video] Música agregada: {Path(musica).name}")
            except Exception as e:
                print(f"[Video] Error con música: {e}")

        if player:
            player.write_log(f"[Video] Exportando slideshow...")

        video_final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            logger=None,
            threads=4,
            fps=24,
        )

        for c in clips:
            try:
                c.close()
            except Exception:
                pass

        return True, str(output_path)

    except Exception as e:
        print(f"[Video] Slideshow error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def _editar_videos(videos, output_path, musica=None, cortar=None, filtro=None, player=None):
    """Edita y une videos usando MoviePy."""
    try:
        from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip
        from moviepy import vfx, afx

        if player:
            player.write_log(f"[Video] Cargando {len(videos)} videos...")

        clips = []
        for v in videos:
            try:
                clip = VideoFileClip(str(v))

                if cortar:
                    inicio = cortar.get("inicio", 0)
                    fin    = min(cortar.get("fin", clip.duration), clip.duration)
                    if inicio < fin:
                        clip = clip.subclipped(inicio, fin)

                if filtro:
                    if filtro == "byn":
                        clip = clip.with_effects([vfx.BlackAndWhite()])
                    elif filtro == "brillo":
                        clip = clip.with_effects([vfx.MultiplyColor(1.3)])
                    elif filtro == "oscuro":
                        clip = clip.with_effects([vfx.MultiplyColor(0.7)])

                clips.append(clip)
            except Exception as e:
                print(f"[Video] Error cargando {v.name}: {e}")
                continue

        if not clips:
            return False, "No pude cargar ningún video."

        video_final = concatenate_videoclips(clips, method="compose") if len(clips) > 1 else clips[0]

        if musica and Path(musica).exists():
            try:
                audio = AudioFileClip(str(musica))
                if audio.duration > video_final.duration:
                    audio = audio.subclipped(0, video_final.duration)
                else:
                    audio = audio.with_effects([afx.AudioLoop(duration=video_final.duration)])
                audio = audio.with_effects([afx.MultiplyVolume(0.4)])
                video_final = video_final.with_audio(audio)
            except Exception as e:
                print(f"[Video] Error con música: {e}")

        video_final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            logger=None,
            threads=4,
        )

        for c in clips:
            try:
                c.close()
            except Exception:
                pass

        return True, str(output_path)

    except Exception as e:
        print(f"[Video] Error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def _abrir_davinci():
    """Abre DaVinci Resolve."""
    for ruta in [
        "C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\Resolve.exe",
        "C:\\Program Files (x86)\\Blackmagic Design\\DaVinci Resolve\\Resolve.exe",
    ]:
        if Path(ruta).exists():
            subprocess.Popen([ruta])
            return True
    return False


def video_editor(parameters, player=None, speak=None):
    """
    Editor de video y slideshow para JARVIS.
    Parametros:
        accion        : slideshow | editar | unir | davinci
        carpeta       : carpeta con fotos o videos
        musica        : nombre o ruta de música
        duracion_foto : segundos por foto en slideshow (default: 3)
        filtro        : byn | brillo | oscuro
        nombre        : nombre del archivo de salida
    """
    accion        = parameters.get("accion", "editar").lower()
    carpeta       = parameters.get("carpeta", "").strip()
    musica        = parameters.get("musica", "").strip()
    duracion_foto = int(parameters.get("duracion_foto", 3))
    filtro        = parameters.get("filtro", "").lower()
    nombre        = parameters.get("nombre", "video_jarvis").strip()

    # Abrir DaVinci
    if accion == "davinci":
        if speak:
            speak("Abriendo DaVinci Resolve, jefe.")
        ok = _abrir_davinci()
        return "DaVinci Resolve abierto." if ok else "No encontré DaVinci Resolve instalado."

    if speak:
        speak("Buscando archivos, jefe.")

    archivos, carpeta_encontrada = _encontrar_archivos(carpeta if carpeta else None)

    if not archivos:
        return (
            "No encontré fotos ni videos en esa carpeta, jefe. "
            "Dígame exactamente dónde están."
        )

    # Separar imágenes y videos
    imagenes = [f for f in archivos if f.suffix.lower() in IMAGE_EXTS]
    videos   = [f for f in archivos if f.suffix.lower() in VIDEO_EXTS]

    if player:
        player.write_log(f"[Video] {len(imagenes)} fotos, {len(videos)} videos en {carpeta_encontrada}")

    # Buscar música
    carpeta_musica = parameters.get("carpeta_musica", "").strip()
    ruta_musica = None
    if musica:
        # Buscar primero en carpeta específica si se dio
        if carpeta_musica and Path(carpeta_musica).exists():
            for ext in AUDIO_EXTS:
                for f in Path(carpeta_musica).glob(f"*{ext}"):
                    if musica.lower() in f.name.lower():
                        ruta_musica = f
                        break
                if ruta_musica:
                    break
        # Si no encontró, buscar en lugares comunes
        if not ruta_musica:
            ruta_musica = _encontrar_musica(musica)
    elif carpeta_musica and Path(carpeta_musica).exists():
        # Tomar cualquier música de la carpeta especificada
        for ext in AUDIO_EXTS:
            archivos_musica = list(Path(carpeta_musica).glob(f"*{ext}"))
            if archivos_musica:
                ruta_musica = archivos_musica[0]
                break
    elif accion in ("slideshow", "editar"):
        ruta_musica = _encontrar_musica()

    # Nombre de salida
    nombre_limpio = "".join(c for c in nombre if c.isalnum() or c in "_- ")
    output_path   = DESKTOP / f"{nombre_limpio}.mp4"
    contador = 1
    while output_path.exists():
        output_path = DESKTOP / f"{nombre_limpio}_{contador}.mp4"
        contador += 1

    # Decidir qué hacer
    if accion == "slideshow" or (imagenes and not videos):
        # Slideshow de fotos
        if not imagenes:
            return "No encontré fotos en esa carpeta, jefe."

        if speak:
            msg = f"Creando slideshow con {len(imagenes)} fotos"
            if ruta_musica:
                msg += " y música"
            msg += f". Cada foto durará {duracion_foto} segundos. Dame un momento, jefe."
            speak(msg)

        ok, resultado = _hacer_slideshow(
            imagenes    = imagenes,
            output_path = output_path,
            musica      = str(ruta_musica) if ruta_musica else None,
            duracion_foto = duracion_foto,
            player      = player,
        )
    else:
        # Editar videos
        if speak:
            msg = f"Editando {len(videos)} videos"
            if ruta_musica:
                msg += " con música"
            msg += ". Dame un momento, jefe."
            speak(msg)

        ok, resultado = _editar_videos(
            videos      = videos,
            output_path = output_path,
            musica      = str(ruta_musica) if ruta_musica else None,
            filtro      = filtro if filtro else None,
            player      = player,
        )

    if ok:
        try:
            subprocess.Popen(["explorer", str(output_path)])
        except Exception:
            pass

        if speak:
            tipo = "slideshow" if (accion == "slideshow" or not videos) else "video"
            speak(
                f"¡Listo jefe! {tipo.capitalize()} creado con "
                f"{len(imagenes) if not videos else len(videos)} archivos"
                + (f" y música" if ruta_musica else "")
                + f". Lo guardé en el escritorio como '{output_path.name}'."
            )

        return f"Creado exitosamente: {output_path}"
    else:
        if speak:
            speak("Tuve un problema, jefe. Abriendo DaVinci Resolve.")
        _abrir_davinci()
        return f"Error: {resultado[:100]}"
