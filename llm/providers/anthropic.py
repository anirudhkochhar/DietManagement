import json
from typing import Any, Literal, cast

import anthropic

from llm.interface import ImageContent, Message, RawResult, TextContent

_MEDIA_TYPE = Literal["image/jpeg", "image/png", "image/gif", "image/webp"]


class AnthropicProvider:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def call(
        self,
        model: str,
        messages: list[Message],
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> RawResult:
        system_parts: list[anthropic.types.TextBlockParam] = []
        anthropic_messages: list[anthropic.types.MessageParam] = []

        for msg in messages:
            if msg.role == "system":
                text = msg.content if isinstance(msg.content, str) else _concat_text(msg.content)
                sys_block: anthropic.types.TextBlockParam = {"type": "text", "text": text}
                system_parts.append(sys_block)
            else:
                anthropic_messages.append(
                    {
                        "role": msg.role,
                        "content": _build_content(
                            msg, response_schema if msg.role == "user" else None
                        ),
                    }
                )

        schema_injected = any(
            isinstance(m["content"], str) and "JSON" in m["content"]
            for m in anthropic_messages
            if m["role"] == "user"
        )
        last_is_user = bool(anthropic_messages) and anthropic_messages[-1]["role"] == "user"
        if response_schema and not schema_injected and last_is_user:
            last = anthropic_messages[-1]
            extra = (
                f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(response_schema)}"
            )
            if isinstance(last["content"], str):
                last["content"] = last["content"] + extra
            elif isinstance(last["content"], list):
                last["content"].append({"type": "text", "text": extra})

        resp = await self._client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_parts if system_parts else anthropic.NOT_GIVEN,  # type: ignore[arg-type]
            messages=anthropic_messages,
        )

        content_text = ""
        for resp_block in resp.content:
            if resp_block.type == "text":
                content_text += resp_block.text

        usage = resp.usage
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0

        return RawResult(
            content=content_text,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=cached,
            model=model,
        )


def _concat_text(parts: list[TextContent | ImageContent]) -> str:
    return " ".join(p.text for p in parts if isinstance(p, TextContent))


def _build_content(
    msg: Message,
    response_schema: dict[str, Any] | None,
) -> str | list[anthropic.types.ContentBlockParam]:
    if isinstance(msg.content, str):
        return msg.content

    blocks: list[anthropic.types.ContentBlockParam] = []
    for part in msg.content:
        if isinstance(part, TextContent):
            blocks.append({"type": "text", "text": part.text})
        elif isinstance(part, ImageContent):
            media_type = cast(_MEDIA_TYPE, part.media_type)
            img_block: anthropic.types.ImageBlockParam = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": part.base64_data,
                },
            }
            blocks.append(img_block)

    return blocks
