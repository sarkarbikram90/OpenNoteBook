"""OpenNotebook — Podcast-Style Audio Overview Script & Pluggable TTS Engine.

Generates engaging two-host ("Alex" & "Sam") grounded audio overview dialogues
from notebook source summaries and chunks, and optionally synthesizes MP3 audio
using OpenAI TTS when configured (gracefully falling back to browser Web Speech
synthesis for 100% local / zero-API-key execution).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_WORDS_PER_SECOND = 2.6

TONE_INSTRUCTIONS: dict[str, str] = {
    "deep_dive": (
        "Host a thoughtful, engaging 2-host podcast deep dive. Unpack technical nuances, "
        "connect ideas across sources, and explain why they matter."
    ),
    "brief": (
        "Deliver a crisp executive briefing. Cover the key takeaways, decisions, and metrics "
        "in 6-8 tight exchanges."
    ),
    "debate": (
        "Stage a constructive two-host debate where Alex highlights strengths and opportunities "
        "while Sam probes trade-offs, risks, and counterarguments grounded in the sources."
    ),
}


@dataclass(frozen=True)
class DialogueTurn:
    """Single spoken line in a two-host Audio Overview."""

    speaker: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"speaker": self.speaker, "text": self.text}


@dataclass(frozen=True)
class AudioOverviewScript:
    """Structured Audio Overview podcast script."""

    title: str
    summary: str
    turns: list[DialogueTurn]
    estimated_duration_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "turns": [t.to_dict() for t in self.turns],
            "estimated_duration_seconds": self.estimated_duration_seconds,
        }


def estimate_duration_seconds(turns: list[DialogueTurn]) -> int:
    """Estimate spoken audio duration from total word count."""
    words = sum(len(t.text.split()) for t in turns)
    return max(15, round(words / _WORDS_PER_SECOND))


def build_dialogue_prompt(
    notebook_name: str,
    source_excerpts: list[tuple[str, str]],
    *,
    focus_topic: str | None = None,
    tone: str = "deep_dive",
) -> str:
    """Build a structured LLM prompt to generate a grounded two-host script."""
    style = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["deep_dive"])
    topic_line = (
        f"Focus especially on: {focus_topic.strip()}\n"
        if focus_topic and focus_topic.strip()
        else ""
    )

    context_blocks = []
    for idx, (src_name, excerpt) in enumerate(source_excerpts[:12], start=1):
        clean_excerpt = excerpt.strip()[:1200]
        context_blocks.append(f"[Source {idx}: {src_name}]\n{clean_excerpt}")
    context = "\n\n".join(context_blocks) or "No source text available."

    return (
        "You are producing a podcast-style Audio Overview for OpenNotebook.\n"
        f"Notebook: {notebook_name}\n"
        f"{topic_line}"
        f"Style: {style}\n\n"
        "Hosts:\n"
        "- Alex: enthusiastic lead researcher who frames key insights.\n"
        "- Sam: analytical co-host who asks sharp questions and connects evidence.\n\n"
        "Rules:\n"
        "1. Ground EVERY claim in the provided source excerpts; reference source names naturally.\n"
        "2. Write 8 to 14 natural spoken turns alternating between Alex and Sam.\n"
        "3. Return ONLY valid JSON matching this schema:\n"
        '{"title": "...", "summary": "1-2 sentence episode description", '
        '"turns": [{"speaker": "Alex", "text": "..."}, {"speaker": "Sam", "text": "..."}]}\n\n'
        f"SOURCE EXCERPTS:\n{context}\n"
    )


def build_fallback_script(
    notebook_name: str,
    source_excerpts: list[tuple[str, str]],
    *,
    focus_topic: str | None = None,
    tone: str = "deep_dive",
) -> AudioOverviewScript:
    """Deterministic extractive dialogue fallback when no LLM is reachable."""
    topic = focus_topic.strip() if focus_topic and focus_topic.strip() else notebook_name
    source_names = list(dict.fromkeys(name for name, _ in source_excerpts if name))
    listed = ", ".join(source_names[:4]) if source_names else "your uploaded documents"

    turns: list[DialogueTurn] = [
        DialogueTurn(
            speaker="Alex",
            text=f"Welcome back to OpenNotebook Audio Studio! Today we're exploring {topic}, drawing directly from {listed}.",
        ),
        DialogueTurn(
            speaker="Sam",
            text=(
                f"We're running this as a {tone.replace('_', ' ')} session across "
                f"{len(source_names) or 1} source(s). Let's jump right into the core findings."
            ),
        ),
    ]

    for idx, (src_name, excerpt) in enumerate(source_excerpts[:4]):
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", excerpt.strip()) if s.strip()]
        snippet = " ".join(sentences[:2])[:280] if sentences else excerpt.strip()[:280]
        speaker = "Alex" if idx % 2 == 0 else "Sam"
        followup_speaker = "Sam" if speaker == "Alex" else "Alex"
        turns.append(
            DialogueTurn(
                speaker=speaker,
                text=f"In {src_name}, a key point stands out: {snippet}",
            )
        )
        turns.append(
            DialogueTurn(
                speaker=followup_speaker,
                text=f"That connects directly back to {topic}—especially when we compare it with the rest of the notebook's evidence.",
            )
        )

    turns.append(
        DialogueTurn(
            speaker="Alex",
            text=f"That wraps up our overview of {topic}. Dive into the Chat or Knowledge Graph tabs to inspect individual citations!",
        )
    )

    return AudioOverviewScript(
        title=f"{notebook_name}: {focus_topic.strip()}" if focus_topic and focus_topic.strip() else f"{notebook_name} — Audio Overview",
        summary=f"Two-host {tone.replace('_', ' ')} synthesis grounded in {listed}.",
        turns=turns,
        estimated_duration_seconds=estimate_duration_seconds(turns),
    )


def parse_dialogue_script(
    raw_text: str,
    notebook_name: str,
    source_excerpts: list[tuple[str, str]],
    *,
    focus_topic: str | None = None,
    tone: str = "deep_dive",
) -> AudioOverviewScript:
    """Parse JSON or transcript-formatted LLM output into an ``AudioOverviewScript``."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # 1. Try JSON parsing (extracting outermost {...} if surrounded by prose)
    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            raw_turns = parsed.get("turns") or []
            turns = [
                DialogueTurn(
                    speaker=str(item.get("speaker") or ("Alex" if i % 2 == 0 else "Sam")).strip(),
                    text=str(item.get("text") or "").strip(),
                )
                for i, item in enumerate(raw_turns)
                if isinstance(item, dict) and str(item.get("text") or "").strip()
            ]
            if turns:
                title = str(parsed.get("title") or f"{notebook_name} — Audio Overview").strip()
                summary = str(parsed.get("summary") or "Grounded two-host notebook briefing.").strip()
                return AudioOverviewScript(
                    title=title[:200],
                    summary=summary[:500],
                    turns=turns,
                    estimated_duration_seconds=estimate_duration_seconds(turns),
                )
        except Exception:
            logger.debug("JSON parse failed for audio overview script; trying line parser")

    # 2. Try "Alex: ..." / "Sam: ..." line format
    line_turns: list[DialogueTurn] = []
    for line in cleaned.splitlines():
        m = re.match(r"^\s*(Alex|Sam|Host\s*1|Host\s*2)\s*:\s*(.+)$", line, re.IGNORECASE)
        if m:
            raw_speaker = m.group(1).strip()
            speaker = "Alex" if raw_speaker.lower() in ("alex", "host 1", "host1") else "Sam"
            line_turns.append(DialogueTurn(speaker=speaker, text=m.group(2).strip()))

    if len(line_turns) >= 2:
        return AudioOverviewScript(
            title=f"{notebook_name} — Audio Overview",
            summary=f"Two-host {tone.replace('_', ' ')} podcast episode generated from notebook sources.",
            turns=line_turns,
            estimated_duration_seconds=estimate_duration_seconds(line_turns),
        )

    return build_fallback_script(
        notebook_name, source_excerpts, focus_topic=focus_topic, tone=tone
    )


async def synthesize_openai_tts(
    turns: list[DialogueTurn],
    *,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
) -> bytes | None:
    """Synthesize multi-speaker MP3 audio using OpenAI TTS when an API key is configured."""
    if not api_key or not turns:
        return None

    import httpx

    voice_map = {"alex": "alloy", "sam": "nova"}
    segments: list[bytes] = []
    url = f"{base_url.rstrip('/')}/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            for turn in turns[:20]:
                voice = voice_map.get(turn.speaker.lower(), "alloy")
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "model": "tts-1",
                        "voice": voice,
                        "input": turn.text[:4096],
                        "response_format": "mp3",
                    },
                )
                resp.raise_for_status()
                segments.append(resp.content)
    except Exception as exc:
        logger.warning("OpenAI TTS synthesis skipped due to error: %s", exc)
        return None

    return b"".join(segments) if segments else None
