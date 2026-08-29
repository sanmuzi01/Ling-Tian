from __future__ import annotations

import json
from dataclasses import replace
from urllib.parse import urlparse
import urllib.request
from typing import Any

from shared.config import Settings


def settings_with_llm_overrides(settings: Settings, overrides: dict[str, Any] | None) -> Settings:
    if not overrides:
        return settings
    enabled = bool(overrides.get("enabled", settings.llm_enabled))
    api_key = str(overrides.get("api_key") or overrides.get("apiKey") or settings.llm_api_key).strip()
    model = str(overrides.get("model") or settings.llm_model).strip()
    base_url = str(overrides.get("base_url") or overrides.get("baseUrl") or settings.llm_base_url).strip()
    return replace(
        settings,
        llm_enabled=enabled,
        llm_api_key=api_key,
        llm_model=model or settings.llm_model,
        llm_base_url=normalize_base_url(base_url or infer_base_url(model)),
    )


def infer_base_url(model: str) -> str:
    normalized = model.strip().lower()
    if normalized.startswith(("deepseek", "deepseek-")):
        return "https://api.deepseek.com/v1"
    if normalized.startswith(("qwen", "qwq", "dashscope")):
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"
    if normalized.startswith(("moonshot", "kimi")):
        return "https://api.moonshot.cn/v1"
    if normalized.startswith(("glm", "chatglm")):
        return "https://open.bigmodel.cn/api/paas/v4"
    if normalized.startswith(("llama", "mistral", "mixtral")):
        return "http://127.0.0.1:11434/v1"
    return "https://api.openai.com/v1"


def normalize_base_url(value: str) -> str:
    base_url = value.strip() or "https://api.openai.com/v1"
    if base_url.endswith("/responses") or base_url.endswith("/chat/completions"):
        base_url = base_url.rsplit("/", 1)[0]
        if base_url.endswith("/chat"):
            base_url = base_url.rsplit("/", 1)[0]
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("LLM base URL must be an http(s) URL")
    return base_url.rstrip("/")


def maybe_compose_with_llm(
    draft_markdown: str,
    evidence: dict[str, Any],
    settings: Settings,
) -> tuple[str, dict[str, Any]]:
    base_url = normalize_base_url(settings.llm_base_url)
    status = {
        "enabled": settings.llm_enabled,
        "provider": "openai-compatible",
        "model": settings.llm_model,
        "base_url": _redacted_base_url(base_url),
        "used": False,
        "mode": "template",
        "reason": "",
    }
    if not settings.llm_enabled:
        status["reason"] = "MINING_AGENT_LLM_ENABLED=false"
        return draft_markdown, status
    if not settings.llm_api_key:
        status["reason"] = "LLM API key is not configured"
        return draft_markdown, status

    try:
        generated, endpoint = _call_llm(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=base_url,
            draft_markdown=draft_markdown,
            evidence=evidence,
        )
    except Exception as exc:  # noqa: BLE001 - LLM is optional and must not break the demo
        status["reason"] = f"LLM request failed: {exc}"
        return draft_markdown, status

    if not _looks_like_valid_brief(generated):
        status["reason"] = "LLM output did not preserve required brief structure"
        return draft_markdown, status
    status["used"] = True
    status["mode"] = "llm"
    status["endpoint"] = endpoint
    status["reason"] = "LLM request completed"
    return generated.rstrip() + "\n", status


def _call_llm(
    api_key: str,
    model: str,
    base_url: str,
    draft_markdown: str,
    evidence: dict[str, Any],
) -> tuple[str, str]:
    if _prefers_responses(base_url, model):
        try:
            return _call_responses(api_key, model, base_url, draft_markdown, evidence), "responses"
        except Exception:
            if "api.openai.com" in base_url:
                raise
    return _call_chat_completions(api_key, model, base_url, draft_markdown, evidence), "chat_completions"


def _call_responses(
    api_key: str,
    model: str,
    base_url: str,
    draft_markdown: str,
    evidence: dict[str, Any],
) -> str:
    body = {
        "model": model,
        "store": False,
        "input": [
            {
                "role": "developer",
                "content": (
                    "你是矿业投研 Agent 的报告生成模块。只能基于用户提供的结构化证据写作，"
                    "不得编造新闻、价格、储量或引用。必须保留 Markdown 标题结构、引用编号和链接。"
                    "不要输出 Markdown 表格。中文表达要专业、简洁。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请基于下面的草稿和证据生成最终中文 Markdown 矿权日报。\n\n"
                    f"草稿:\n{draft_markdown}\n\n"
                    f"结构化证据 JSON:\n{json.dumps(evidence, ensure_ascii=False)[:24000]}"
                ),
            },
        ],
    }
    request = urllib.request.Request(
        f"{base_url}/responses",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    output_text = payload.get("output_text")
    if output_text:
        return str(output_text)
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(str(content["text"]))
    if chunks:
        return "\n".join(chunks)
    raise ValueError("Responses API returned no text output")


def _call_chat_completions(
    api_key: str,
    model: str,
    base_url: str,
    draft_markdown: str,
    evidence: dict[str, Any],
) -> str:
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是矿业投研 Agent 的报告生成模块。只能基于用户提供的结构化证据写作，"
                    "不得编造新闻、价格、储量或引用。必须保留 Markdown 标题结构、引用编号和链接。"
                    "不要输出 Markdown 表格。中文表达要专业、简洁。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请基于下面的草稿和证据生成最终中文 Markdown 矿权日报。\n\n"
                    f"草稿:\n{draft_markdown}\n\n"
                    f"结构化证据 JSON:\n{json.dumps(evidence, ensure_ascii=False)[:24000]}"
                ),
            },
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    choices = payload.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        if message.get("content"):
            return str(message["content"])
    raise ValueError("Chat Completions API returned no message content")


def _prefers_responses(base_url: str, model: str) -> bool:
    normalized = model.lower()
    return "api.openai.com" in base_url or normalized.startswith(("gpt-", "o1", "o3", "o4"))


def _redacted_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def _looks_like_valid_brief(markdown: str) -> bool:
    required = [
        "# ",
        "## 1. 执行摘要",
        "## 2. 资产动态与新闻证据",
        "## 3. 资源量 / 储量信息",
        "## 4. 价格走势",
        "## 5. 风险提示",
        "## 7. 引用来源",
    ]
    return all(item in markdown for item in required) and "|---" not in markdown
