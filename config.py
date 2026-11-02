# config.py
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


PROJECT_DIR = Path(__file__).resolve().parent # 项目路径
load_dotenv(PROJECT_DIR / ".env") # 读取.env文件


def get_model_name() -> str: # 获取模型名称
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not model:
        raise ValueError("请在 .env 中填写 OPENAI_MODEL")
    return model


def create_client() -> OpenAI: # 获取APIKEY
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("请在 .env 中填写 OPENAI_API_KEY")

    options = {
        "api_key": api_key,
        "timeout": 90.0, # 设置请求超时
        "max_retries": 0, # 限制自动请求次数
    }

    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    if base_url:
        options["base_url"] = base_url

    return OpenAI(**options)