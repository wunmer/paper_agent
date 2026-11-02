import argparse
import json
import re
from pathlib import Path
from typing import Any

import pymupdf

BASE_DIR = Path(__file__).resolve().parent
PAPER_DIR = BASE_DIR / "data" / "papers"
METADATA_PATH = PAPER_DIR / "metadata.json"
STORAGE_DIR = BASE_DIR / "storage"
CHUNKS_PATH = STORAGE_DIR / "chunks.json"
TESSDATA_DIR = BASE_DIR / "models" / "tessdata"


def normalize_text(text: str) -> str:
    """清理PDF解析产生的多余空白和不可见字符。"""
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def split_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[str]:
    """使用固定长度滑动窗口切块。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size必须大于0")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap必须满足 0 <= overlap < chunk_size")

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def load_metadata() -> list[dict[str, Any]]:
    if not METADATA_PATH.exists():
        raise FileNotFoundError(f"找不到元数据文件：{METADATA_PATH}")

    with METADATA_PATH.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    if not isinstance(metadata, list):
        raise ValueError("metadata.json最外层必须是JSON数组")

    return metadata

def extract_page_text(page) -> tuple[str, str]:
    """优先直接提取文字，无文字时执行整页OCR。"""
    text = page.get_text("text", sort=True)

    if text.strip():
        return text, "native"

    language_file = TESSDATA_DIR / "eng.traineddata"

    if not language_file.exists():
        raise FileNotFoundError(f"找不到OCR语言包：{language_file}")

    textpage = page.get_textpage_ocr(
        language="eng",
        dpi=300,
        full=True,
        tessdata=str(TESSDATA_DIR),
    )

    text = page.get_text(
        "text",
        textpage=textpage,
        sort=True,
    )

    return text, "ocr"


def extract_paper_chunks(
    paper: dict[str, Any],
    chunk_size: int = 1200,
    overlap: int = 200,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    pdf_path = PAPER_DIR / paper["file"]

    if not pdf_path.exists():
        raise FileNotFoundError(f"找不到PDF：{pdf_path}")

    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages必须大于0")

    paper_chunks = []

    # 保存逐页文本，用于人工检查
    text_dir = STORAGE_DIR / "extracted" / paper["paper_id"]
    text_dir.mkdir(parents=True, exist_ok=True)

    with pymupdf.open(pdf_path) as document:
        page_count = len(document)

        if max_pages is not None:
            page_count = min(page_count, max_pages)

        for page_index in range(page_count):
            page_number = page_index + 1
            page = document[page_index]

            print(f"正在处理第{page_number}页……", flush=True)

            raw_text, method = extract_page_text(page)

            # 保留换行的原始结果，便于对照PDF查看
            text_path = text_dir / f"page_{page_number:03d}.txt"
            text_path.write_text(raw_text, encoding="utf-8")

            page_text = normalize_text(raw_text)

            print(
                f"方式={method}，字符数={len(page_text)}",
                flush=True,
            )

            if not page_text:
                print(f"警告：第{page_number}页仍未识别到文字")
                continue

            page_chunks = split_text(
                page_text,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            for chunk_number, chunk_text in enumerate(
                page_chunks, start=1
            ):
                paper_chunks.append({
                    "chunk_id": (
                        f"{paper['paper_id']}"
                        f"-p{page_number}"
                        f"-c{chunk_number}"
                    ),
                    "paper_id": paper["paper_id"],
                    "title": paper["title"],
                    "year": paper.get("year"),
                    "topic": paper.get("topic"),
                    "file": paper["file"],
                    # PDF文件中的第几页，不一定等于印刷页码
                    "page": page_number,
                    "text": chunk_text,
                    "extraction_method": method,
                })

    return paper_chunks



def main() -> None:
    metadata = load_metadata()
    all_chunks = []

    for paper in metadata:
        text_dir = STORAGE_DIR / "extracted" / paper["paper_id"]
        page_files = sorted(text_dir.glob("page_*.txt"))

        if not page_files:
            raise FileNotFoundError(
                f"未找到逐页文本：{text_dir}"
            )

        paper_chunk_count = 0

        for text_path in page_files:
            # page_001.txt → 1
            page_number = int(text_path.stem.split("_")[-1])

            raw_text = text_path.read_text(encoding="utf-8")
            page_text = normalize_text(raw_text)

            if not page_text:
                print(f"警告：空文本，跳过 {text_path.name}")
                continue

            for chunk_number, chunk_text in enumerate(
                split_text(page_text), start=1
            ):
                all_chunks.append({
                    "chunk_id": (
                        f"{paper['paper_id']}"
                        f"-p{page_number}"
                        f"-c{chunk_number}"
                    ),
                    "paper_id": paper["paper_id"],
                    "title": paper["title"],
                    "year": paper.get("year"),
                    "topic": paper.get("topic"),
                    "file": paper["file"],
                    "page": page_number,
                    "text": chunk_text,
                    "extraction_method": "cached_text",
                })
                paper_chunk_count += 1

        print(
            f"{paper['file']}："
            f"读取{len(page_files)}页，"
            f"生成{paper_chunk_count}个文本块"
        )

    if not all_chunks:
        raise RuntimeError("没有生成文本块，保留原索引文件")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    # 先写临时文件，写入成功后再替换正式索引
    temp_path = CHUNKS_PATH.with_suffix(".tmp")

    temp_path.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    temp_path.replace(CHUNKS_PATH)

    print(f"\n已保存{len(all_chunks)}个文本块")
    print(f"保存位置：{CHUNKS_PATH}")
    

if __name__ == "__main__":
    main()



    