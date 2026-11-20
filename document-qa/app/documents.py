import re
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader


class DocumentInputError(ValueError):
    pass


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class Chunk:
    page_number: int
    ordinal: int
    content: str


def extract_pages(filename: str, data: bytes, max_pages: int) -> list[PageText]:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == "txt":
        try:
            text = data.decode("utf-8-sig").strip()
        except UnicodeDecodeError as exc:
            raise DocumentInputError("Text files must use UTF-8 encoding.") from exc
        pages = [PageText(1, text)] if text else []
    elif suffix == "pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentInputError("The uploaded file is not a valid PDF.")
        try:
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise DocumentInputError("Password-protected PDFs are not supported.")
            if len(reader.pages) > max_pages:
                raise DocumentInputError(f"PDFs are limited to {max_pages} pages.")
            pages = [PageText(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
        except DocumentInputError:
            raise
        except Exception as exc:
            raise DocumentInputError("Could not read this PDF. Check that it is not corrupted or password-protected.") from exc
        pages = [PageText(p.page_number, p.text.strip()) for p in pages if p.text.strip()]
    else:
        raise DocumentInputError("Only PDF and UTF-8 TXT files are supported.")
    if not pages:
        raise DocumentInputError("No selectable text was found. Scanned/image-only PDFs need OCR and are not supported yet.")
    return pages


def chunk_pages(pages: list[PageText], chunk_words: int, overlap_words: int) -> list[Chunk]:
    if chunk_words < 1 or overlap_words < 0 or overlap_words >= chunk_words:
        raise ValueError("Chunk size and overlap settings are invalid.")
    chunks: list[Chunk] = []
    for page in pages:
        words = re.findall(r"\S+", page.text)
        start = 0
        while start < len(words):
            end = min(start + chunk_words, len(words))
            content = " ".join(words[start:end]).strip()
            if content:
                chunks.append(Chunk(page.page_number, len(chunks), content))
            if end == len(words):
                break
            start = end - overlap_words
    return chunks
