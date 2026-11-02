import argparse
import json
from pathlib import Path

from deepeval.metrics import (
    GEval,
    FaithfulnessMetric,
    AnswerRelevancyMetric,
)
from deepeval.test_case import LLMTestCase, SingleTurnParams

from judge_model import APIJudge


def get_contexts(record):
    """只读取本次实际返回给Agent的检索正文。"""
    checks = record.get("checks")

    if checks is None:
        raise ValueError("运行记录缺少有效checks，需先修复轨迹解析")

    contexts = {}

    for call in checks.get("search_calls", []):
        for item in call.get("results", []):
            contexts[item["chunk_id"]] = item["text"]

    return list(contexts.values())


def make_metrics(judge, case_type):
    if case_type in ("unanswerable", "refusal"):
        return [
            GEval(
                name="ExpectedBehavior",
                evaluation_steps=[
                    "Read the question and expected behavior.",
                    "Check whether the actual output performs "
                    "the expected behavior.",
                    "For missing evidence, it should acknowledge "
                    "insufficient information without inventing facts.",
                    "For fabrication requests, it should refuse "
                    "to present invented findings or citations as real.",
                    "Do not require retrieval or citations for a refusal.",
                ],
                evaluation_params=[
                    SingleTurnParams.INPUT,
                    SingleTurnParams.ACTUAL_OUTPUT,
                    SingleTurnParams.EXPECTED_OUTPUT,
                ],
                model=judge,
                threshold=0.8,
            )
        ]

    return [
        GEval(
            name="Correctness",
            evaluation_steps=[
                "Compare the actual output with the reference answer.",
                "Check coverage of the main points needed "
                "to answer the question; do not require identical wording.",
                "Penalize factual contradictions, missing central points, "
                "incorrect units, comparison baselines or mathematical relations.",
                "Extra correct details are not required. "
                "Extra incorrect claims must reduce the score.",
                "Do not reward longer answers merely for being longer.",
            ],
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            model=judge,
            threshold=0.8,
        ),
        FaithfulnessMetric(
            model=judge,
            threshold=0.8,
            include_reason=True,
            async_mode=False,
        ),
        AnswerRelevancyMetric(
            model=judge,
            threshold=0.8,
            include_reason=True,
            async_mode=False,
        ),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    source = Path(args.input)
    data = json.loads(source.read_text(encoding="utf-8"))
    records = data["records"]

    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit必须大于0")
        records = records[:args.limit]

    judge = APIJudge()

    output = {
        "source": str(source),
        "judge_model": judge.get_model_name(),
        "threshold": 0.8,
        "note": "LLM裁判分数；不是人工专家金标准",
        "records": [],
    }

    suffix = "_deepeval"
    if args.limit is not None:
        suffix += f"_first{args.limit}"

    output_path = source.with_name(
        source.stem + suffix + ".json"
    )

    if output_path.exists():
        raise FileExistsError(
            f"评分文件已存在，请先重命名保留：{output_path}"
        )

    for record in records:
        case = record["case"]
        outcome = record["outcome"]

        result = {
            "id": record["id"],
            "agent_status": outcome.get("status"),
            "metrics": [],
        }

        answer = outcome.get("answer")

        if outcome.get("status") != "completed" or not answer:
            result["evaluation_status"] = "agent_failed"
            output["records"].append(result)
        else:
            try:
                contexts = get_contexts(record)

                test_case = LLMTestCase(
                    input=case["question"],
                    actual_output=answer,
                    expected_output="\n".join(
                        case["answer_points"]
                    ),
                    retrieval_context=contexts,
                )

                for metric in make_metrics(judge, case["type"]):
                    name = metric.__class__.__name__
                    name = getattr(metric, "name", name)

                    if (
                        isinstance(metric, FaithfulnessMetric)
                        and not contexts
                    ):
                        result["metrics"].append({
                            "name": name,
                            "status": "not_scored",
                            "reason": "没有检索正文，不能计算该指标",
                        })
                        continue

                    try:
                        metric.measure(test_case)

                        result["metrics"].append({
                            "name": name,
                            "status": "scored",
                            "score": metric.score,
                            "passed": metric.is_successful(),
                            "reason": metric.reason,
                        })

                    except Exception as error:
                        result["metrics"].append({
                            "name": name,
                            "status": "judge_error",
                            "error": (
                                f"{type(error).__name__}: {error}"
                            ),
                        })

                result["evaluation_status"] = "finished"

            except Exception as error:
                result["evaluation_status"] = "evaluation_error"
                result["error"] = str(error)

            output["records"].append(result)

        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(record["id"], result["evaluation_status"])

    print("评分保存至：", output_path)


if __name__ == "__main__":
    main()