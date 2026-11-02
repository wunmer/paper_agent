import argparse
import csv
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from agent import chat_with_tools


BASE_DIR = Path(__file__).resolve().parent
CASES_PATH = BASE_DIR / "eval" / "cases.json"
CHUNKS_PATH = BASE_DIR / "storage" / "chunks.json"
RESULT_DIR = BASE_DIR / "eval" / "results"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_search_calls(trace):
    """从轨迹中提取每次search_papers的完整结果。"""
    if not isinstance(trace, list):
        raise ValueError("trace必须是列表")

    calls = []

    for step in trace:
        tool_name = step.get("tool", step.get("tool_name"))

        if tool_name != "search_papers":
            continue

        observation = step.get(
            "observation",
            step.get("result"),
        )

        if isinstance(observation, str):
            try:
                observation = json.loads(observation)
            except json.JSONDecodeError as error:
                raise ValueError(
                    "search_papers轨迹只保存了摘要，"
                    "请保存完整工具结果"
                ) from error

        if not isinstance(observation, dict):
            raise ValueError(
                "search_papers的observation必须是字典"
            )

        results = observation.get("results")

        if observation.get("ok") is True:
            if not isinstance(results, list):
                raise ValueError("检索轨迹缺少完整results列表")

            if any(
                not isinstance(item, dict)
                or "chunk_id" not in item
                or "text" not in item
                for item in results
            ):
                raise ValueError(
                    "检索轨迹缺少chunk_id或正文"
                )
        else:
            results = []

        calls.append({
            "args": step.get("args", {}),
            "ok": observation.get("ok"),
            "error": observation.get("error"),
            "results": results,
        })

    return calls


def evidence_coverage(groups, retrieved_ids):
    """
    每组命中任一可接受证据块即算覆盖。
    这是已标注证据组覆盖率，不是全库Recall。
    """
    if not groups:
        return None

    hits = sum(
        bool(
            set(group["acceptable_chunk_ids"])
            & retrieved_ids
        )
        for group in groups
    )

    return hits / len(groups)


def automatic_checks(case, outcome):
    calls = parse_search_calls(outcome.get("trace", []))

    first_ids = {
        item["chunk_id"]
        for item in calls[0]["results"][:5]
    } if calls else set()

    all_items = [
        item
        for call in calls
        for item in call["results"]
    ]

    all_ids = {item["chunk_id"] for item in all_items}

    answer = outcome.get("answer") or ""
    if not isinstance(answer, str):
        raise ValueError("answer应为字符串或None")

    # 只检查答案中直接出现的已返回chunk_id。
    # 若模型省略chunk_id，留待人工检查引用。
    cited_returned_ids = sorted(
        chunk_id
        for chunk_id in all_ids
        if chunk_id in answer
    )

    groups = case.get("evidence_groups", [])

    return {
        "search_call_count": len(calls),
        "first_search_top5_group_coverage":
            evidence_coverage(groups, first_ids),
        "all_searches_group_coverage":
            evidence_coverage(groups, all_ids),
        "retrieved_chunk_ids": sorted(all_ids),
        "cited_returned_chunk_ids": cited_returned_ids,
        "search_calls": calls,
    }


def save_outputs(records, output_stem, metadata):
    json_path = output_stem.with_suffix(".json")

    json_path.write_text(
        json.dumps(
            {"metadata": metadata, "records": records},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    csv_path = output_stem.with_suffix(".csv")

    fieldnames = [
        "id", "type", "status", "elapsed_seconds",
        "search_call_count",
        "first_search_top5_group_coverage",
        "all_searches_group_coverage",
        "correctness_0_2",
        "faithfulness_pass_fail",
        "citation_validity_pass_fail_na",
        "citation_support_pass_fail_na",
        "expected_behavior_pass_fail",
        "failure_stage",
        "notes",
    ]

    with csv_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            checks = record.get("checks") or {}

            row = {
                "id": record["id"],
                "type": record["type"],
                "status": record["outcome"].get("status"),
                "elapsed_seconds": record["elapsed_seconds"],
                "search_call_count":
                    checks.get("search_call_count"),
                "first_search_top5_group_coverage":
                    checks.get(
                        "first_search_top5_group_coverage"
                    ),
                "all_searches_group_coverage":
                    checks.get("all_searches_group_coverage"),
            }

            writer.writerow(row)

    lines = ["# Agent评测报告", ""]

    for record in records:
        case = record["case"]

        lines.extend([
            f"## {record['id']}：{case['question']}",
            "",
            f"状态：{record['outcome'].get('status')}",
            f"耗时：{record['elapsed_seconds']}秒",
            "",
            "### 参考答案要点",
            "",
            *[
                f"- {point}"
                for point in case["answer_points"]
            ],
            "",
            "### 实际回答",
            "",
            record["outcome"].get("answer") or "（无回答）",
            "",
            "### 自动检查",
            "",
            "```json",
            json.dumps(
                {
                    key: value
                    for key, value in
                    (record.get("checks") or {}).items()
                    if key != "search_calls"
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
        ])

        if record.get("evaluation_error"):
            lines.extend([
                "评测记录错误："
                + record["evaluation_error"],
                "",
            ])

        for index, call in enumerate(
            (record.get("checks") or {}).get(
                "search_calls", []
            ),
            start=1,
        ):
            lines.extend([
                f"### 第{index}次检索",
                "",
                "参数：" + json.dumps(
                    call["args"], ensure_ascii=False
                ),
                "",
            ])

            for item in call["results"]:
                lines.extend([
                    f"**{item['chunk_id']}**",
                    "",
                    item["text"],
                    "",
                ])

    output_stem.with_suffix(".md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split", choices=["dev", "test"], default="dev"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--label", default="baseline")
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit必须大于0")

    cases = read_json(CASES_PATH)
    chunks = read_json(CHUNKS_PATH)

    chunk_ids = {item["chunk_id"] for item in chunks}
    corpus_hash = hashlib.sha256(
        CHUNKS_PATH.read_bytes()
    ).hexdigest()

    selected = [
        case for case in cases
        if case["split"] == args.split
    ]

    if args.limit is not None:
        selected = selected[:args.limit]

    if not selected:
        raise ValueError("没有选中评测题")

    for case in selected:
        if case.get("annotation_status") != "verified":
            raise ValueError(
                f"{case['id']}尚未完成标注"
            )

        expected_hash = case.get("corpus_sha256")
        if expected_hash and expected_hash != corpus_hash:
            raise ValueError(
                "chunks.json与评测集绑定的语料版本不同"
            )

        for group in case.get("evidence_groups", []):
            ids = group["acceptable_chunk_ids"]

            if not ids or not set(ids) <= chunk_ids:
                raise ValueError(
                    f"{case['id']}证据块ID为空或不存在"
                )

    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_stem = RESULT_DIR / (
        f"{args.label}_{args.split}_{stamp}"
    )

    metadata = {
        "split": args.split,
        "label": args.label,
        "corpus_sha256": corpus_hash,
        "cases_sha256": hashlib.sha256(
            CASES_PATH.read_bytes()
        ).hexdigest(),
        "max_rounds": 6,
        "started_at": datetime.now().isoformat(),
    }

    records = []

    for case in selected:
        print(
            f"\n正在评测 {case['id']}："
            f"{case['question']}",
            flush=True,
        )

        start = time.perf_counter()

        try:
            # 每次调用都应在函数内部新建messages，
            # 不共享上一道题的对话历史。
            outcome = chat_with_tools(
                case["question"],
                max_rounds=6,
            )

            if not isinstance(outcome, dict):
                raise TypeError(
                    "chat_with_tools必须返回字典"
                )

        except Exception as error:
            outcome = {
                "answer": None,
                "trace": [],
                "status": "error",
                "error": f"{type(error).__name__}: {error}",
            }

        elapsed = round(time.perf_counter() - start, 2)

        try:
            checks = automatic_checks(case, outcome)
            evaluation_error = None
        except (ValueError, TypeError, KeyError) as error:
            checks = None
            evaluation_error = str(error)

        records.append({
            "id": case["id"],
            "type": case["type"],
            "case": case,
            "outcome": outcome,
            "elapsed_seconds": elapsed,
            "checks": checks,
            "evaluation_error": evaluation_error,
        })

        # 每完成一题就保存，避免中途出错丢失全部结果。
        save_outputs(records, output_stem, metadata)

        print(
            f"完成：{outcome.get('status')}，"
            f"耗时{elapsed}秒",
            flush=True,
        )

        if evaluation_error:
            print(
                "轨迹格式需要修复：" + evaluation_error
            )
            break

    print(f"\n结果文件前缀：{output_stem}")


if __name__ == "__main__":
    main()