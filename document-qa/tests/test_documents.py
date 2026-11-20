from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.documents import DocumentInputError, PageText, chunk_pages, extract_pages


def test_text_extract_and_utf8():
    pages = extract_pages("notes.TXT", "café and notes".encode(), 10)
    assert pages[0].text == "café and notes"


def test_pdf_extracts_page_text():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (Hello from a searchable PDF) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    pages = extract_pages("sample.pdf", output.getvalue(), 10)
    assert "searchable PDF" in pages[0].text


@pytest.mark.parametrize(("filename", "content", "message"), [
    ("notes.docx", b"x", "Only PDF"),
    ("notes.pdf", b"not-pdf", "valid PDF"),
    ("notes.txt", b"\xff", "UTF-8"),
])
def test_invalid_document_inputs(filename, content, message):
    with pytest.raises(DocumentInputError, match=message):
        extract_pages(filename, content, 10)


def test_scanned_or_empty_pdf_is_rejected():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    with pytest.raises(DocumentInputError, match="OCR"):
        extract_pages("scan.pdf", output.getvalue(), 10)


def test_chunk_size_overlap_and_page_boundary():
    chunks = chunk_pages([PageText(1, "one two three four five six seven"), PageText(3, "other page")], 4, 1)
    assert [chunk.page_number for chunk in chunks] == [1, 1, 3]
    assert chunks[0].content == "one two three four"
    assert chunks[1].content.startswith("four five")


def test_invalid_chunk_configuration_rejected():
    with pytest.raises(ValueError):
        chunk_pages([PageText(1, "text")], 10, 10)
