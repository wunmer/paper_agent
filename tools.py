# tools.py
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import validate
from rank_bm25 import BM25Okapi

# 增加路径
BASE_DIR = Path(__file__).resolve().parent
CHUNKS_PATH = BASE_DIR / "storage" / "chunks.json"

# 分词函数
def tokenize(text: str) -> list[str]:
    """
    面向英文论文的简单分词：
    统一小写并保留英文、数字及连字符。
    """
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())


# 处理对象的元数据类型
METADATA_PATH = BASE_DIR / "data" / "papers" / "metadata.json"

def load_papers() -> dict[str, dict[str, Any]]:
    with METADATA_PATH.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    papers = {}

    for paper in metadata:
        paper_id = paper["paper_id"]

        if paper_id in papers:
            raise ValueError(f"论文ID重复：{paper_id}")

        papers[paper_id] = {
            key: value
            for key, value in paper.items()
            if key != "paper_id"
        }

    return papers

PAPERS = load_papers()



# list_papers函数
def list_papers() -> dict[str, Any]:
    """返回论文 ID 和标题，不返回年份。"""
    return {
        "ok": True,
        "papers": [
            {"paper_id": paper_id, "title": info["title"]}
            for paper_id, info in PAPERS.items()
        ],
    }

# 
def get_paper_info(paper_id: str) -> dict[str, Any]:
    """根据论文 ID 查询完整元数据。"""
    if paper_id not in PAPERS:
        return {
            "ok": False,
            "error": "paper_not_found",
            "paper_id": paper_id,
        }

    return {
        "ok": True,
        "paper_id": paper_id,
        **PAPERS[paper_id],
    }

# JSON schema
LIST_PAPERS_PARAMS = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

GET_PAPER_INFO_PARAMS = {
    "type": "object",
    "properties": {
        "paper_id": {
            "type": "string",
            "description": "本地论文 ID，例如 p1。应从目录工具获取。",
        }
    },
    "required": ["paper_id"],
    "additionalProperties": False,
}


# 给模型看的工具定义
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_papers",
            "description": (
                "列出本地论文库的论文 ID 和标题。"
                "不知道目标论文 ID 时，先调用这个工具。"
            ),
            "parameters": LIST_PAPERS_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_paper_info",
            "description": (
                "根据本地论文 ID 查询标题、年份和主题。"
                "必须使用本地目录中存在的 ID，不要猜测。"
            ),
            "parameters": GET_PAPER_INFO_PARAMS,
        },
    },
]


# TOOLS告诉模型函数如何请求/调用，TOOL_REGISTRY告诉模型可调用的模型
TOOL_REGISTRY = {
    "list_papers": {
        "function": list_papers,
        "schema": LIST_PAPERS_PARAMS,
    },
    "get_paper_info": {
        "function": get_paper_info,
        "schema": GET_PAPER_INFO_PARAMS,
    },
}

# 工具使用：解码，校验，执行
def run_tool(name: str, arguments: str) -> dict[str, Any]:
    if name not in TOOL_REGISTRY:
        raise ValueError(f"unknown_tool: {name}")

    tool = TOOL_REGISTRY[name]

    # 语法校验：JSON 字符串 → Python 对象
    args = json.loads(arguments)

    # 结构校验：字段、类型、必填项
    validate(instance=args, schema=tool["schema"])

    # 执行实际函数
    return tool["function"](**args)


if __name__ == "__main__":
    print(run_tool("list_papers", "{}"))

    print(run_tool(
        "get_paper_info",
        '{"paper_id": "p2"}',
    ))

    print(run_tool(
        "get_paper_info",
        '{"paper_id": "p999"}',
    ))



# -----------BM25检索器-------------- #
class BM25PaperRetriever:
    def __init__(self, chunks_path: Path):
        if not chunks_path.exists():
            raise FileNotFoundError(
                f"找不到文本块文件：{chunks_path}，请先运行python ingest.py"
            )

        with chunks_path.open("r", encoding="utf-8") as file:
            self.chunks: list[dict[str, Any]] = json.load(file)

        if not self.chunks:
            raise ValueError("chunks.json为空，请检查PDF解析结果")

        tokenized_corpus = [
            tokenize(chunk["title"] + " " + chunk["text"])
            for chunk in self.chunks
        ]

        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("query不能为空")

        if not 1 <= top_k <= 10:
            raise ValueError("top_k必须在1到10之间")

        query_tokens = tokenize(query)

        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )

        results = []

        for index in ranked_indices:
            score = float(scores[index])

            # 没有关键词匹配时，BM25得分通常为0
            if score <= 0:
                continue

            chunk = self.chunks[index]

            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "paper_id": chunk["paper_id"],
                    "title": chunk["title"],
                    "page": chunk["page"],
                    "score": round(score, 4),
                    "text": chunk["text"],
                }
            )

            if len(results) >= top_k:
                break

        return results

# 初始化检索器+声明工具函数

_retriever: BM25PaperRetriever | None = None

def get_retriever() -> BM25PaperRetriever:
    global _retriever

    if _retriever is None:
        _retriever = BM25PaperRetriever(CHUNKS_PATH)

    return _retriever


def search_papers(query: str, top_k: int = 5) -> dict[str, Any]:
    """
    使用BM25检索本地论文文本块。
    """
    try:
        results = get_retriever().search(query, top_k)

        return {
            "ok": True,
            "query": query,
            "retrieval_method": "bm25",
            "result_count": len(results),
            "results": results,
        }

    except (FileNotFoundError, ValueError) as error:
        return {
            "ok": False,
            "query": query,
            "error": str(error),
            "results": [],
        }

SEARCH_PAPERS_PARAMS = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "minLength": 1,
            "description": (
                "英文检索关键词。中文问题先转换为英文关键词，"
                "保留TRIPOD、AUC等专有名词。"
            ),
        },
        "top_k": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "description": "返回文本块数量，建议5。",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

TOOLS.append({
    "type": "function",
    "function": {
        "name": "search_papers",
        "description": (
            "使用BM25检索本地论文正文。"
            "查询论文定义、方法、结论、比较时调用。"
            "返回正文证据、论文标题、paper_id、PDF页序号及chunk_id。"
            "结果可能包含OCR误识别；词语匹配不代表证据充分。"
        ),
        "parameters": SEARCH_PAPERS_PARAMS,
    },
})

TOOL_REGISTRY["search_papers"] = {
    "function": search_papers,
    "schema": SEARCH_PAPERS_PARAMS,
}