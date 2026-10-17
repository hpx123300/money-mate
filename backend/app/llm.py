"""LLM 客户端：调 OpenAI 兼容的 /chat/completions 接口（默认 DeepSeek）。

不引入额外依赖（用标准库 urllib），换供应商只改环境变量：
    LLM_API_KEY  密钥
    LLM_BASE_URL 接口地址，默认 https://api.deepseek.com
    LLM_MODEL    模型名，默认 deepseek-chat
"""

import json
import time
import urllib.request
import urllib.error

from .config import settings

# 瞬时故障重试：网络抖动、超时、429、5xx 值得重试；4xx 客户端错误不重试
MAX_ATTEMPTS = 3
BACKOFF_BASE = 0.6


class LLMError(Exception):
    """LLM 调用失败（没配 key / 网络错误 / 返回不合法）。"""


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, (urllib.error.URLError, TimeoutError)):
        return True
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or 500 <= exc.code < 600
    return False


def _open_with_retry(req: urllib.request.Request, timeout: int):
    """发送请求，对瞬时故障做指数退避重试。"""
    last: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            last = e
            if not _retryable(e):
                body = e.read().decode("utf-8", "ignore")[:200]
                raise LLMError(f"LLM 接口报错（HTTP {e.code}）：{body}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(BACKOFF_BASE * (2**attempt))
    raise LLMError(f"LLM 接口重试 {MAX_ATTEMPTS} 次仍失败：{last}") from last


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
    with _open_with_retry(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    try:
        data = json.loads(raw)
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


def chat_text_stream(prompt: str, system: str, temperature: float = 0.4):
    """流式版 chat_text：逐块 yield 文本片段（生成器）。

    用 SSE 协议解析 OpenAI 兼容接口的流式响应，
    不引入额外依赖（标准库 urllib 逐行读取）。
    """
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
        "stream": True,
    }
    req = urllib.request.Request(
        f"{settings.llm_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
    )
    resp = _open_with_retry(req, timeout=60)

    with resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                delta = chunk["choices"][0]["delta"].get("content")
                if delta:
                    yield delta
            except (json.JSONDecodeError, KeyError, IndexError):
                continue



def chat_tools(
    messages: list[dict],
    tools: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 800,
) -> dict:
    """带工具调用的一轮对话（Function Calling）。

    返回 {"content": str, "tool_calls": [{"id","name","arguments"}]}。
    只负责「问模型要什么工具」，不负责执行——执行与回填由调用方做，
    这样工具实现和模型客户端解耦，测试时可以只 mock 这一层。
    """
    if not settings.llm_api_key:
        raise LLMError("未配置 LLM_API_KEY，请在 .env 或部署平台环境变量里设置")

    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        f"{settings.llm_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
    )
    with _open_with_retry(req, timeout=45) as resp:
        raw = resp.read().decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMError("LLM 返回的不是合法 JSON") from e

    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError("LLM 返回内容格式不对") from e

    calls = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        calls.append(
            {
                "id": tc.get("id") or "",
                "name": fn.get("name") or "",
                "arguments": fn.get("arguments") or "{}",
            }
        )
    return {"content": (message.get("content") or "").strip(), "tool_calls": calls}
