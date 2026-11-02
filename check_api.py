# # check_api.py
# from config import create_client, get_model_name


# def main():
#     client = create_client()

#     response = client.chat.completions.create(
#         model=get_model_name(),
#         messages=[
#             {"role": "user", "content": "请只回复：连接成功"}
#         ],
#     )

#     print(response.choices[0].message.content)


# if __name__ == "__main__":
#     main()


import time
from config import create_client, get_model_name


def main():
    client = create_client()
    model = get_model_name()

    print(f"正在调用模型：{model}", flush=True)
    start = time.perf_counter()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "Reply only: OK"}
        ],
        reasoning_effort="low",
        max_tokens=128,
        timeout=90.0,
    )

    print(f"耗时：{time.perf_counter() - start:.1f} 秒")
    print("结束原因：", response.choices[0].finish_reason)
    print("回答：", response.choices[0].message.content)


if __name__ == "__main__":
    main()