from tools import search_papers


def main() -> None:
    queries = [
        "prediction model calibration",
        "risk of bias in prediction model studies",
        "reporting guideline for prediction models",
    ]

    for query in queries:
        print("\n" + "=" * 70)
        print(f"Query: {query}")

        response = search_papers(query=query, top_k=3)

        if not response["ok"]:
            print(f"检索失败：{response['error']}")
            continue

        for rank, result in enumerate(response["results"], start=1):
            print(f"\n结果{rank}")
            print(f"论文：{result['title']}")
            print(f"页码：{result['page']}")
            print(f"BM25分数：{result['score']}")
            print(f"文本：{result['text'][:300]}...")


if __name__ == "__main__":
    main()