import json
from typing import Any

import openai

from llm.interface import ImageContent, Message, RawResult, TextContent

_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


class DeepSeekProvider:
    def __init__(self, api_key: str, base_url: str = _DEEPSEEK_BASE_URL) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def call(
        self,
        model: str,
        messages: list[Message],
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> RawResult:
        oai_messages = [_to_oai_message(m) for m in messages]

        if response_schema:
            schema_note = (
                f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(response_schema)}"
            )
            for m in reversed(oai_messages):
                if m["role"] == "user":
                    content = m["content"]
                    if isinstance(content, str):
                        m["content"] = content + schema_note
                    elif isinstance(content, list):
                        content.append({"type": "text", "text": schema_note})
                    break

        resp = await self._client.chat.completions.create(
            model=model,
            messages=oai_messages,  # type: ignore[arg-type]
            max_tokens=4096,
        )

        choice = resp.choices[0]
        content_text = choice.message.content or ""
        usage = resp.usage

        return RawResult(
            content=content_text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            cached_tokens=0,
            model=model,
        )


def _to_oai_message(msg: Message) -> dict[str, Any]:
    if isinstance(msg.content, str):
        return {"role": msg.role, "content": msg.content}

    parts: list[dict[str, Any]] = []
    for part in msg.content:
        if isinstance(part, TextContent):
            parts.append({"type": "text", "text": part.text})
        elif isinstance(part, ImageContent):
            data_uri = f"data:{part.media_type};base64,{part.base64_data}"
            parts.append({"type": "image_url", "image_url": {"url": data_uri}})

    return {"role": msg.role, "content": parts}
