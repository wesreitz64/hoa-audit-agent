"""
PDF Utility — Extract text from individual pages using PyMuPDF.

This is the foundation layer. Every agent in the swarm receives
text from this utility rather than touching the raw PDF directly.
"""

import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass


@dataclass
class PDFPage:
    """A single extracted page from a PDF."""
    page_number: int  # 1-indexed (matches source_page in schemas)
    text: str
    total_pages: int
    source_file: str


def extract_pages(pdf_path: str | Path) -> list[PDFPage]:
    """
    Extract text from every page of a PDF.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of PDFPage objects, one per page, 1-indexed.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    pages = []

    for i, page in enumerate(doc):
        text = page.get_text()
        pages.append(
            PDFPage(
                page_number=i + 1,  # 1-indexed to match source_page fields
                text=text.strip(),
                total_pages=len(doc),
                source_file=pdf_path.name,
            )
        )

    doc.close()
    return pages


def extract_page_range(pdf_path: str | Path, start: int, end: int) -> list[PDFPage]:
    """
    Extract text from a specific range of pages (1-indexed, inclusive).

    Useful for testing or processing a subset of pages.
    """
    all_pages = extract_pages(pdf_path)
    return [p for p in all_pages if start <= p.page_number <= end]


if __name__ == "__main__":
    """Quick test: show first 5 pages of a sample PDF."""
    import sys

    if len(sys.argv) < 2:
        # Default to the Feb 2026 packet
        pdf = "data/sample_pdfs/Briarwyck Monthly Financials 2026 2.pdf"
    else:
        pdf = sys.argv[1]

    pages = extract_pages(pdf)
    print(f"📄 {Path(pdf).name}: {len(pages)} pages\n")

    for page in pages[:5]:
        lines = [l for l in page.text.split("\n") if l.strip()]
        print(f"── Page {page.page_number} ({len(lines)} lines)")
        for line in lines[:8]:
            print(f"   {line.strip()}")
        if len(lines) > 8:
            print(f"   ... ({len(lines) - 8} more lines)")
        print()
