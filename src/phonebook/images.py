"""Prepare page photos for the LLM (no LLM, free)."""

import base64
import io
from pathlib import Path

from langchain_core.messages.content import ImageContentBlock
from PIL import Image, ImageOps

PAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MAX_SIDE = 1568  # bigger images cost more tokens but are not read better


def list_pages(folder: str | Path) -> list[str]:
    """All page images in a folder, sorted by file name."""
    return sorted(str(p) for p in Path(folder).iterdir() if p.suffix.lower() in PAGE_SUFFIXES)


def image_block(path: str | Path, max_side: int = MAX_SIDE) -> ImageContentBlock:
    """A page as an image block for a chat message: rotated upright, made smaller, JPEG."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")  # fix phone-camera rotation
        img.thumbnail((max_side, max_side))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
    data = base64.b64encode(buffer.getvalue()).decode()
    return {"type": "image", "base64": data, "mime_type": "image/jpeg"}
