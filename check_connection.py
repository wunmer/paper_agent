from config import create_client

client = create_client()

print("正在查询模型列表……", flush=True)
models = client.models.list()

print("连接成功，返回的部分模型：")
for model in models.data[:10]:
    print(model.id)