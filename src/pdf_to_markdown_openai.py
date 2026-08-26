"""OCR PDFs to Markdown with OpenAI's PDF-capable vision model."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def convert(pdf_path: str | Path) -> Path:
    pdf_path = Path(pdf_path)
    output_path = pdf_path.with_suffix(".openai.md")
    if output_path.exists() and output_path.stat().st_size:
        return output_path

    client = OpenAI()
    with pdf_path.open("rb") as file:
        uploaded = client.files.create(file=file, purpose="user_data")
    response = client.responses.create(
        model="gpt-5",
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": (
                    "OCR toàn bộ tài liệu này. Trả về Markdown tiếng Việt, "
                    "giữ nguyên tiêu đề, đoạn văn, danh sách và bảng. "
                    "Không giải thích thêm."
                )},
                {"type": "input_file", "file_id": uploaded.id},
            ],
        }],
    )
    markdown = response.output_text.strip()
    if not markdown:
        raise RuntimeError(f"OpenAI returned no Markdown for {pdf_path}")
    output_path.write_text(markdown + "\n", encoding="utf-8")
    return output_path


if __name__ == "__main__":
    for filename in sys.argv[1:]:
        print(f"{filename} -> {convert(filename)}", flush=True)
