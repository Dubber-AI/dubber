import asyncio
import os
from typing import Any

import httpx
from openai import AsyncOpenAI

from dubber.application.ports.translator import TranslatorProvider
from dubber.application.dto.config import TranslatorConfig
from dubber.domain.entities import Subtitle, SubtitleBlock

_SYSTEM_PROMPT = (
    "Ты профессиональный переводчик технических курсов. "
    "Переводи английские субтитры на русский язык.\n"
    "Требования:\n"
    "* сохраняй смысл;\n"
    "* сохраняй стиль преподавателя;\n"
    "* сохраняй техническую терминологию;\n"
    "* не добавляй комментарии;\n"
    "* не добавляй пояснений;\n"
    "* не меняй порядок блоков;\n"
    "* не удаляй текст;\n"
    "* количество выходных блоков должно совпадать с количеством входных блоков;\n"
    "* возвращай только перевод.\n\n"
    "Не переводи без необходимости:\n"
    "Python, JavaScript, TypeScript, Node.js, Docker, Kubernetes, FastAPI, Django, Flask, "
    "PostgreSQL, Redis, MongoDB, OpenAI, Anthropic, Claude, Gemini, Qdrant, Weaviate, "
    "LangChain, LlamaIndex, Git, GitHub, Linux.\n\n"
    "Формат ответа: верни JSON-объект с полем 'blocks', содержащим массив строк. "
    "Каждая строка — перевод соответствующего блока."
)

_DONT_TRANSLATE = {
    "Python", "JavaScript", "TypeScript", "Node.js", "Docker", "Kubernetes",
    "FastAPI", "Django", "Flask", "PostgreSQL", "Redis", "MongoDB",
    "OpenAI", "Anthropic", "Claude", "Gemini", "Qdrant", "Weaviate",
    "LangChain", "LlamaIndex", "Git", "GitHub", "Linux",
}


class OpenRouterTranslatorProvider(TranslatorProvider):
    def __init__(self, config: TranslatorConfig) -> None:
        self._config = config
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        self._client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=config.timeout,
            http_client=httpx.AsyncClient(
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            ),
        )
        self._semaphore = asyncio.Semaphore(5)

    async def healthcheck(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    async def translate_batch(
        self, blocks: list[SubtitleBlock]
    ) -> list[SubtitleBlock]:
        if not blocks:
            return []

        texts = [self._block_to_text(b) for b in blocks]
        payload = {"blocks": texts}
        import json

        response_text = await self._call_with_retry(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ]
        )
        translated_texts = self._extract_translated(response_text, len(blocks))

        result: list[SubtitleBlock] = []
        for block, trans_text in zip(blocks, translated_texts, strict=False):
            translated_subs = [
                Subtitle(
                    index=sub.index,
                    start=sub.start,
                    end=sub.end,
                    text=trans_text,
                )
                for sub in block.subtitles
            ]
            result.append(SubtitleBlock(translated_subs))
        return result

    def _block_to_text(self, block: SubtitleBlock) -> str:
        return "\n".join(s.text for s in block.subtitles)

    def _extract_translated(self, response_text: str, expected_count: int) -> list[str]:
        import json
        import re

        # Try to parse JSON from the response
        try:
            data = json.loads(response_text)
            if isinstance(data, dict) and "blocks" in data:
                return list(data["blocks"])[:expected_count]
        except json.JSONDecodeError:
            pass

        # Fallback: extract quoted strings or lines
        # Try markdown code blocks
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict) and "blocks" in data:
                    return list(data["blocks"])[:expected_count]
            except json.JSONDecodeError:
                pass

        # Last resort: split by newlines and take non-empty lines
        lines = [line.strip() for line in response_text.splitlines() if line.strip()]
        if len(lines) >= expected_count:
            return lines[:expected_count]

        # If count mismatch, pad with original texts (should not happen)
        return lines + [""] * (expected_count - len(lines))

    async def _call_with_retry(self, messages: list[dict[str, Any]]) -> str:
        for attempt in range(self._config.max_retries):
            async with self._semaphore:
                try:
                    response = await self._client.chat.completions.create(
                        model=self._config.model,
                        messages=messages,  # type: ignore[arg-type]
                        temperature=0.3,
                        max_tokens=4096,
                    )
                    content = response.choices[0].message.content or ""
                    return content.strip()
                except Exception as exc:
                    status = getattr(exc, "status_code", None)
                    if status in {429, 500, 502, 503, 504}:
                        delay = self._config.base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                    if attempt == self._config.max_retries - 1:
                        raise
                    await asyncio.sleep(self._config.base_delay)
        raise RuntimeError("Max retries exceeded for translation")
