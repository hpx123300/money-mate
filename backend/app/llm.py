"""LLM 客户端：调 OpenAI 兼容的 /chat/completions 接口（默认 DeepSeek）。

不引入额外依赖（用标准库 urllib），换供应商只改环境变量：
    LLM_API_KEY  密钥
    LLM_BASE_URL 接口地址，默认 https://api.deepseek.com
    LLM_MODEL    模型名，默认 deepseek-chat
"""

import json
import urllib.request
import urllib.error

from .config import settings


class LLMError(Exception):
    """LLM 调用失败（没配 key / 网络错误 / 返回不合法）。"""


def _chat(prompt: str, system: str, json_mode: bool = False, temperature: float = 0.2) -> str:
    if not settings.llm_api_key:
        raise LLMError("未配置 LLM_API_KEY，请在 .env 或部署平台环境变量里设置")

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": 800,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    req = urllib.request.Request(
        f"{settings.llm_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise LLMError(f"LLM 接口报错（HTTP {e.code}）：{e.read().decode('utf-8', 'ignore')[:200]}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise LLMError(f"LLM 接口连不上：{e}") from e
    except json.JSONDecodeError as e:
        raise LLMError("LLM 返回的不是合法 JSON") from e

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError("LLM 返回内容格式不对") from e


def _extract_json(text: str) -> dict:
    """从模型输出里取出 JSON 对象（容忍 ```json 代码块包裹）。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("LLM 没有返回 JSON")
    return json.loads(text[start : end + 1])


def chat_json(prompt: str, system: str) -> dict:
    """让模型只输出一个 JSON 对象。"""
    return _extract_json(_chat(prompt, system, json_mode=True))


def chat_text(prompt: str, system: str) -> str:
    """让模型输出一段自然语言。"""
    return _chat(prompt, system, json_mode=False)
