from pathlib import Path
import pymupdf

path = Path("data/papers/decision curve analysis.pdf").resolve()
print("实际文件：", path)

with pymupdf.open(path) as doc:
    print("页数：", len(doc))
    print("需要密码：", doc.needs_pass)

    for i in range(min(3, len(doc))):
        page = doc[i]
        text = page.get_text("text")
        print(f"\n第{i + 1}页")
        print("文本字符数：", len(text))
        print("文字片段数：", len(page.get_text("words")))
        print("引用图片数：", len(page.get_images()))
        print("矢量绘图数：", len(page.get_drawings()))
        print("文本预览：", repr(text[:200]))