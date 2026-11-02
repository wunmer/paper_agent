from pathlib import Path
import pymupdf

BASE_DIR = Path(__file__).resolve().parent

PDF_PATH = BASE_DIR / "data" / "papers" / "decision curve analysis.pdf"

# 改为你实际存放eng.traineddata的文件夹
TESSDATA_DIR = Path(r"D:\paper-agent\models\tessdata")

if not (TESSDATA_DIR / "eng.traineddata").exists():
    raise FileNotFoundError(
        f"找不到英文语言包：{TESSDATA_DIR / 'eng.traineddata'}"
    )

with pymupdf.open(PDF_PATH) as doc:
    page = doc[0]

    print("正在识别第一页，请稍候……")

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

    print("识别字符数：", len(text))
    print("正文预览：")
    print(text[:2000])