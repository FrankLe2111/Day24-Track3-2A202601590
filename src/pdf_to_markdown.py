"""Convert scanned PDFs to Markdown with the local Hugging Face GLM-OCR model."""

from __future__ import annotations

import argparse
import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
MODEL_ID = os.getenv("GLMOCR_MODEL", "zai-org/GLM-OCR")


def pdf_to_markdown(pdf_path: str | Path, output_path: str | Path | None = None) -> Path:
    """OCR every page locally and save Markdown next to the PDF."""
    try:
        import pymupdf
        import torch
        from PIL import Image
        from transformers import AutoTokenizer
        try:
            from transformers import AutoModelForMultimodalLM
        except ImportError:  # Transformers 4.57 uses this name instead.
            from transformers import AutoModelForImageTextToText as AutoModelForMultimodalLM
    except ImportError as exc:
        raise RuntimeError("Install local OCR dependencies: pip install pymupdf pillow transformers") from exc

    pdf_path = Path(pdf_path)
    output_path = Path(output_path or pdf_path.with_suffix(".ocr.md"))
    if output_path.exists():
        return output_path

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForMultimodalLM.from_pretrained(
        MODEL_ID, torch_dtype="auto", device_map="auto"
    )
    pages = []
    with pymupdf.open(pdf_path) as document:
        for page_number, page in enumerate(document, 1):
            image = Image.open(BytesIO(page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png"))).convert("RGB")
            messages = [{"role": "user", "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": "Extract all content from this page. Return clean Markdown, preserving headings, paragraphs, lists, and tables."},
            ]}]
            inputs = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=True,
                return_dict=True, return_tensors="pt",
            ).to(model.device)
            with torch.inference_mode():
                outputs = model.generate(**inputs, max_new_tokens=4096)
            text = tokenizer.decode(outputs[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()
            if text:
                pages.append(f"\n<!-- Page {page_number} -->\n\n{text}")

    markdown = "\n".join(pages).strip()
    if not markdown:
        raise RuntimeError(f"GLM-OCR returned no Markdown for {pdf_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert PDF scans to Markdown with local GLM-OCR")
    parser.add_argument("pdf", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    for pdf in args.pdf:
        output = args.output_dir / f"{pdf.stem}.ocr.md" if args.output_dir else None
        print(f"{pdf} -> {pdf_to_markdown(pdf, output)}")


if __name__ == "__main__":
    main()
