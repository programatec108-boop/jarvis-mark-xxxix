# memory_manager.py - Memoria persistente de JARVIS Mark XXXIX
# Cada usuario tiene su propia memoria en su PC
# Archivo: C:\Users\jose1\Mark-XXXIX\memory\memory_manager.py

import json
import os
import time
from pathlib import Path

# Guardar en AppData del usuario - cada usuario tiene la suya
def _get_memory_path() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    mem_dir = Path(appdata) / "JARVIS_Mark39"
    mem_dir.mkdir(parents=True, exist_ok=True)
    return mem_dir / "memory.json"

MEMORY_PATH = _get_memory_path()

_DEFAULT_MEMORY = {
    "version": "1.0",
    "created": time.strftime("%Y-%m-%d"),
    "personal": {},       # nombre, edad, trabajo, etc
    "preferencias": {},   # musica, comida, hobbies
    "proyectos": {},      # proyectos actuales
    "contactos": {},      # gente importante
    "rutinas": {},        # habitos y rutinas
    "notas": {},          # notas generales
}


def load_memory() -> dict:
    """Carga la memoria del usuario desde AppData."""
    try:
        if MEMORY_PATH.exists():
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            # Asegurarse que tiene todas las categorias
            for k, v in _DEFAULT_MEMORY.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        print(f"[Memory] Error cargando: {e}")
    return dict(_DEFAULT_MEMORY)


def save_memory(memory: dict):
    """Guarda la memoria en AppData."""
    try:
        MEMORY_PATH.write_text(
            json.dumps(memory, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[Memory] Error guardando: {e}")


def update_memory(updates: dict):
    """
    Actualiza la memoria con nuevos datos.
    updates = {"categoria": {"clave": {"value": "valor", "timestamp": "..."}}}
    """
    memory = load_memory()
    for categoria, datos in updates.items():
        if categoria not in memory:
            memory[categoria] = {}
        if isinstance(datos, dict):
            for clave, valor in datos.items():
                if isinstance(valor, dict):
                    memory[categoria][clave] = {
                        "value": valor.get("value", str(valor)),
                        "updated": time.strftime("%Y-%m-%d %H:%M")
                    }
                else:
                    memory[categoria][clave] = {
                        "value": str(valor),
                        "updated": time.strftime("%Y-%m-%d %H:%M")
                    }
    save_memory(memory)
    print(f"[Memory] Actualizada: {list(updates.keys())}")


def forget(categoria: str, clave: str = None):
    """Elimina un recuerdo especifico o toda una categoria."""
    memory = load_memory()
    if categoria in memory:
        if clave:
            memory[categoria].pop(clave, None)
            print(f"[Memory] Olvidado: {categoria}.{clave}")
        else:
            memory[categoria] = {}
            print(f"[Memory] Categoria eliminada: {categoria}")
    save_memory(memory)


def clear_all():
    """Borra toda la memoria."""
    save_memory(dict(_DEFAULT_MEMORY))
    print("[Memory] Memoria borrada completamente.")


def format_memory_for_prompt(memory: dict) -> str:
    """Formatea la memoria para incluir en el system prompt de JARVIS."""
    if not memory:
        return ""

    lines = ["[MEMORIA DEL USUARIO — Lo que JARVIS recuerda de ti]"]
    has_content = False

    categories = {
        "personal":     "Información personal",
        "preferencias": "Preferencias y gustos",
        "proyectos":    "Proyectos actuales",
        "contactos":    "Contactos importantes",
        "rutinas":      "Rutinas y hábitos",
        "notas":        "Notas importantes",
    }

    for cat_key, cat_name in categories.items():
        data = memory.get(cat_key, {})
        if data:
            lines.append(f"\n{cat_name}:")
            for clave, val in data.items():
                if isinstance(val, dict):
                    lines.append(f"  - {clave}: {val.get('value', '')}")
                else:
                    lines.append(f"  - {clave}: {val}")
            has_content = True

    if not has_content:
        return ""

    lines.append("\nUsa esta información para personalizar tus respuestas de forma natural.")
    lines.append("No menciones explícitamente que 'recuerdas' algo — solo úsalo naturalmente.\n")
    return "\n".join(lines)


def get_memory_summary() -> str:
    """Resumen de cuánto recuerda JARVIS."""
    memory = load_memory()
    total = sum(len(v) for v in memory.values() if isinstance(v, dict))
    size  = MEMORY_PATH.stat().st_size if MEMORY_PATH.exists() else 0
    size_str = f"{size} B" if size < 1024 else f"{size//1024} KB"
    return f"{total} recuerdos guardados ({size_str})"
