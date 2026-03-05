import asyncio
import os
import re
import uuid

RENDERED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "rendered")

_manim_bin: str | None = None


async def _resolve_manim_bin() -> str:
    global _manim_bin
    if _manim_bin:
        return _manim_bin

    venv_manim = os.path.join(os.path.dirname(RENDERED_DIR), ".venv", "bin", "manim")
    if os.path.isfile(venv_manim):
        _manim_bin = venv_manim
    else:
        _manim_bin = "manim"
    return _manim_bin


async def _find_file_recursive(directory: str, ext: str) -> str | None:
    try:
        entries = os.listdir(directory)
    except OSError:
        return None
    for entry in entries:
        full = os.path.join(directory, entry)
        if os.path.isdir(full):
            found = await _find_file_recursive(full, ext)
            if found:
                return found
        elif entry.endswith(ext):
            return full
    return None


async def render_manim_diagram(code: str, animated: bool = False, caption: str = "") -> str:
    manim = await _resolve_manim_bin()
    short_id = uuid.uuid4().hex[:8]
    py_file = os.path.join(RENDERED_DIR, f"diagram_{short_id}.py")
    out_name = f"diagram_{short_id}"

    class_match = re.search(r"class\s+(\w+)\s*\(\s*(?:Scene|ThreeDScene|MovingCameraScene)\s*\)", code)
    scene_name = class_match.group(1) if class_match else "DiagramScene"

    if not animated and re.search(r"self\.play\s*\(", code):
        animated = True

    os.makedirs(RENDERED_DIR, exist_ok=True)
    with open(py_file, "w") as f:
        f.write(code)

    if animated:
        args = [manim, "render", "-ql", "--format=mp4", "--media_dir", RENDERED_DIR, py_file, scene_name]
    else:
        args = [manim, "render", "-ql", "-s", "--format=png", "--media_dir", RENDERED_DIR, py_file, scene_name]

    ext = ".mp4" if animated else ".png"
    media_subdir = "videos" if animated else "images"

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        proc.kill()
        _cleanup(py_file)
        raise RuntimeError("Manim render timed out (60s)")

    _cleanup(py_file)

    if proc.returncode != 0:
        err_text = (stderr or b"").decode()[:500]
        raise RuntimeError(f"Manim render failed: {err_text}")

    base_dir = os.path.join(RENDERED_DIR, media_subdir, f"diagram_{short_id}")
    output_file = await _find_file_recursive(base_dir, ext)
    if not output_file:
        raise RuntimeError(f"No {ext} found in {base_dir}")

    final_name = f"{out_name}{ext}"
    final_path = os.path.join(RENDERED_DIR, final_name)
    os.rename(output_file, final_path)

    # Clean up nested directory
    import shutil
    shutil.rmtree(base_dir, ignore_errors=True)

    return f"/rendered/{final_name}"


def _cleanup(py_file: str):
    try:
        os.unlink(py_file)
    except OSError:
        pass
