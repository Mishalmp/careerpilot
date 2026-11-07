"""Reading text out of an uploaded CV: PDF, Word (.docx), plain text, or a picture of one.

The file is only ever held in memory while it is read: it is never stored and never executed. What
comes out is plain text, which is then read by the same rules as a pasted CV.

Safety, because the file is untrusted input:
- the size, page count and extracted text are all capped;
- the type is decided by the first bytes of the file, never by its name or declared type;
- a Word file is read with a regular expression over its XML, not an XML parser (no entity-expansion
  attacks), and its unpacked size is checked first (zip bombs);
- nothing in the file is followed: no links, no macros, no embedded files.

Scanned CVs (a PDF or picture with no text in it) need OCR. OCR is an optional extra
(`uv sync --extra ocr`); without it the reader says so and asks for pasted text instead.
"""

import functools
import html
import importlib
import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_BYTES = 5_000_000
MAX_PAGES = 25
MAX_CHARS = 60_000  # the same cap as a pasted CV
MAX_UNPACKED_BYTES = 20_000_000
MIN_TEXT_CHARS = 40  # below this a PDF is treated as a scan
ALLOWED_NAMES = ".pdf, .docx, .txt, .md, .png, .jpg"


class CvReadError(Exception):
    """The file could not be read. The message is written for the person who uploaded it."""


@dataclass(frozen=True)
class CvText:
    text: str
    source: str  # pdf | docx | text | ocr
    notes: list[str]


# An OCR engine turns image bytes into text. A factory returns None when the optional extra is not
# installed, and is only called when a file really needs OCR (starting the engine takes seconds).
OcrEngine = Callable[[bytes], str]
OcrFactory = Callable[[], OcrEngine | None]


OCR_SCALE = (
    2  # measured: at the original size the engine often glues words together ("SeniorPython")
)
OCR_MAX_WIDTH = 2400  # never enlarge a picture past this many pixels wide
_ENLARGE_BELOW = OCR_MAX_WIDTH // OCR_SCALE
_LOWER_L_FOR_I = re.compile(r"(?<=[A-Z]{2})l(?=s?\b)")


def fix_ocr(text: str) -> str:
    """Repair the one slip OCR makes constantly in a CV: a lower-case l read for a capital I, as in
    "APls" and "FastAPl"."""
    return _LOWER_L_FOR_I.sub("I", text)


def _enlarge(image: bytes) -> bytes:
    """The picture drawn twice as large (as PNG): this is what stops OCR gluing words together."""
    with Image.open(io.BytesIO(image)) as picture:
        rgb = picture.convert("RGB")
        if rgb.width < _ENLARGE_BELOW:
            rgb = rgb.resize(
                (rgb.width * OCR_SCALE, rgb.height * OCR_SCALE), Image.Resampling.LANCZOS
            )
        out = io.BytesIO()
        rgb.save(out, format="PNG")
        return out.getvalue()


@functools.cache
def default_ocr() -> OcrEngine | None:
    try:
        module = importlib.import_module("rapidocr_onnxruntime")  # the optional `ocr` extra
    except ImportError:
        return None
    engine: Any = module.RapidOCR()

    def run(image: bytes) -> str:
        try:
            prepared = _enlarge(image)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise CvReadError("This picture could not be read. Is it damaged?") from exc
        found = cast("list[list[Any]] | None", engine(prepared)[0])  # [box, text, confidence] rows
        return fix_ocr(chr(10).join(str(line[1]) for line in found or []))

    return run


def safe_filename(name: str | None) -> str | None:
    """The file name only: no folders, no control characters, bounded length."""
    if not name:
        return None
    base = re.split(r"[\\/]", name)[-1]
    base = "".join(ch for ch in base if ch.isprintable())[:120].strip()
    return base or None


def sniff(data: bytes) -> str | None:
    """pdf, docx, png, jpg, or None, from the first bytes."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    return None


def _clean(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\x00", " ").splitlines()]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):  # at most one blank line in a row
            out.append(line)
    return "\n".join(out).strip()


def _need_ocr(what: str) -> CvReadError:
    return CvReadError(
        f"This {what} has no text in it (it looks scanned). Reading it needs OCR, which is not "
        "installed: run `uv sync --extra ocr` in apps/api, or paste the CV text instead."
    )


def _pdf(data: bytes, ocr_factory: OcrFactory) -> CvText:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise CvReadError("This PDF is password protected. Remove the password and try again.")
        pages = reader.pages[:MAX_PAGES]
        notes: list[str] = []
        if len(reader.pages) > MAX_PAGES:
            notes.append(f"Only the first {MAX_PAGES} of {len(reader.pages)} pages were read.")
        text = _clean("\n".join(page.extract_text() or "" for page in pages))
        if len(text) >= MIN_TEXT_CHARS:
            return CvText(text, "pdf", notes)
        # No text layer: a scan. Its pages are pictures inside the PDF.
        ocr = ocr_factory()
        if ocr is None:
            raise _need_ocr("PDF")
        images = [image.data for page in pages for image in page.images]
        if not images:
            raise CvReadError("This PDF has no text and no pictures to read.")
        text = _clean("\n".join(ocr(image) for image in images[:MAX_PAGES]))
        if len(text) < MIN_TEXT_CHARS:
            raise CvReadError("OCR could not find readable text in this PDF.")
        return CvText(text, "ocr", [*notes, "Read with OCR: check the skills it found."])
    except CvReadError:
        raise
    except (PyPdfError, ValueError, KeyError, OSError, NotImplementedError) as exc:
        raise CvReadError("This PDF could not be read. Is it damaged?") from exc


_PARAGRAPH = re.compile(r"</w:p>|<w:br\s*/?>|<w:tab\s*/?>")
_TAG = re.compile(r"<[^>]+>")


def _docx(data: bytes) -> CvText:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = {i.filename: i for i in archive.infolist()}
            document = info.get("word/document.xml")
            if document is None:
                raise CvReadError("This file is a zip, but not a Word document.")
            if sum(i.file_size for i in info.values()) > MAX_UNPACKED_BYTES:
                raise CvReadError("This document is too large to read.")
            xml = archive.read(document).decode("utf-8", errors="replace")
    except zipfile.BadZipFile as exc:
        raise CvReadError("This Word file could not be read. Is it damaged?") from exc
    text = html.unescape(_TAG.sub("", _PARAGRAPH.sub("\n", xml)))
    return CvText(_clean(text), "docx", [])


def _image(data: bytes, ocr_factory: OcrFactory) -> CvText:
    ocr = ocr_factory()
    if ocr is None:
        raise _need_ocr("picture")
    text = _clean(ocr(data))
    if len(text) < MIN_TEXT_CHARS:
        raise CvReadError("OCR could not find readable text in this picture.")
    return CvText(text, "ocr", ["Read with OCR: check the skills it found."])


def _plain(data: bytes) -> CvText:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CvReadError(f"This file type is not supported. Use {ALLOWED_NAMES}.") from exc
    if sum(not (ch.isprintable() or ch in "\n\r\t") for ch in text) > len(text) // 20:
        raise CvReadError(f"This file type is not supported. Use {ALLOWED_NAMES}.")
    return CvText(_clean(text), "text", [])


def read_cv(data: bytes, ocr: OcrFactory) -> CvText:
    """The text of an uploaded CV. Raises CvReadError (a plain message) when it cannot be read."""
    if not data:
        raise CvReadError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise CvReadError(f"The file is larger than {MAX_BYTES // 1_000_000} MB.")
    kind = sniff(data)
    if kind == "pdf":
        result = _pdf(data, ocr)
    elif kind == "docx":
        result = _docx(data)
    elif kind in ("png", "jpg"):
        result = _image(data, ocr)
    else:
        result = _plain(data)
    notes = list(result.notes)
    text = result.text
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        notes.append(f"Only the first {MAX_CHARS:,} characters were used.")
    if len(text) < MIN_TEXT_CHARS:
        raise CvReadError("Very little text was found in this file. Is it the right one?")
    return CvText(text, result.source, notes)
