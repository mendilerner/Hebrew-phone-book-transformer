"""Prepare page photos for the LLM (no LLM, free)."""

import base64
import io
from pathlib import Path

from langchain_core.messages.content import ImageContentBlock
from PIL import Image, ImageOps

PAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
# The 5.x Claude models read images up to 2576 px on the long side (older ones: 1568).
# Bigger images cost more tokens, but small handwriting needs the pixels.
MAX_SIDE = 2576
MIN_CROP_SIDE = 1000  # small crops are made bigger, so the model sees the letters well


def list_pages(folder: str | Path) -> list[str]:
    """All page images in a folder, sorted by file name."""
    return sorted(str(p) for p in Path(folder).iterdir() if p.suffix.lower() in PAGE_SUFFIXES)


def load_page(path: str | Path) -> Image.Image:
    """The page photo, rotated upright (phone cameras save the rotation apart), as RGB."""
    with Image.open(path) as img:
        return ImageOps.exif_transpose(img).convert("RGB")


def to_block(img: Image.Image, max_side: int = MAX_SIDE) -> ImageContentBlock:
    """An image as a block for a chat message: not bigger than max_side, JPEG."""
    img = img.copy()
    img.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    data = base64.b64encode(buffer.getvalue()).decode()
    return {"type": "image", "base64": data, "mime_type": "image/jpeg"}


def image_block(path: str | Path, max_side: int = MAX_SIDE) -> ImageContentBlock:
    return to_block(load_page(path), max_side)


def crop_block(img: Image.Image, box: tuple[int, int, int, int]) -> ImageContentBlock:
    """A part of the page (box in pixels: left, top, right, bottom), in full resolution."""
    left, top, right, bottom = box
    left, top = max(0, left), max(0, top)
    right, bottom = min(img.width, right), min(img.height, bottom)
    part = img.crop((left, top, right, bottom))
    long_side = max(part.size)
    if long_side < MIN_CROP_SIDE:
        scale = MIN_CROP_SIDE / long_side
        part = part.resize((round(part.width * scale), round(part.height * scale)), Image.LANCZOS)
    return to_block(part)
