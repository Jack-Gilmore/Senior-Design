
import re
import sys
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
from ollama import chat


def extract_numbers(pdf_path):
    pdf_path = Path(pdf_path)

    if not pdf_path.is_file():
        print(f"Error: PDF not found: {pdf_path}")
        return

    all_text = []

    # Open the PDF and process each page
    with fitz.open(pdf_path) as pdf:
        with tempfile.TemporaryDirectory() as temp_dir:
            for page_num, page in enumerate(pdf, start=1):
                print(f"Reading page {page_num} of {len(pdf)}...")

                # First, try extracting selectable text directly
                text = page.get_text("text").strip()

                # If no text exists, use GLM-OCR on a page image
                if not text:
                    image_path = Path(temp_dir) / f"page_{page_num}.png"

                    # Render the PDF page as an image
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(2, 2),
                        alpha=False
                    )
                    pix.save(str(image_path))

                    # Ask GLM-OCR to transcribe the page
                    response = chat(
                        model="glm-ocr",
                        messages=[
                            {
                                "role": "user",
                                "content": (
                                    "Transcribe all text in this document "
                                    "page exactly. Preserve every number, "
                                    "decimal point, sign, percentage, and "
                                    "scientific notation. Do not summarize."
                                ),
                                "images": [str(image_path)]
                            }
                        ]
                    )

                    text = response.message.content

                all_text.append(text)

    # Find integers, decimals, signed numbers, percentages,
    # comma-separated numbers, and scientific notation.
    number_pattern = (
        r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)"
        r"(?:\.\d+)?"
        r"(?:[eE][-+]?\d+)?"
        r"%?"
    )

    full_text = "\n".join(all_text)
    numbers = re.findall(number_pattern, full_text)

    print("\n--- Numbers found in PDF ---")

    if numbers:
        for number in numbers:
            print(number)
    else:
        print("No numbers found.")

    print(f"\nTotal numbers found: {len(numbers)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Usage: python extract_numbers.py "document.pdf"')
    else:
        extract_numbers(sys.argv[1])
