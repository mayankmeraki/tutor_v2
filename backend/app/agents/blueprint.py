"""Session Blueprint — frozen configuration for a session.

The blueprint captures all decisions made at session start:
  - Which prompt sections to load (and in what order)
  - Which tools to enable
  - Which UI panes to show
  - Whether it's study or practice mode

Once created, the blueprint is frozen and stored in the session document.
On session restore, the blueprint is loaded directly (no re-classification).

Prompt caching depends on the static block being identical across turns.
The section order is:
  1. CORE sections (always loaded, same for every session)
  2. DOMAIN sections (loaded based on mode, same for the entire session)
  3. TOOLKIT + TAGS + VOICE (always loaded, after domain)
  4. --- cache boundary ---
  5. DYNAMIC context (changes every turn, never cached)

Classification uses Haiku for freeform text inputs. When mode is explicit
(from UI buttons), classification is skipped — the blueprint is built directly.
"""

from __future__ import annotations

import enum
import json
import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


class SessionMode(str, enum.Enum):
    GENERAL = "general"
    DSA = "dsa"
    SYSTEM_DESIGN = "sd"
    MOCK_INTERVIEW = "mock_interview"


class Interaction(str, enum.Enum):
    STUDY = "study"
    PRACTICE = "practice"


class UILayout(str, enum.Enum):
    BOARD = "board"
    BOARD_EDITOR = "board_editor"
    BOARD_CANVAS = "board_canvas"
    BOARD_EDITOR_CANVAS = "board_editor_canvas"


CORE_SECTIONS = [
    "IDENTITY",
    "STUDENT_CALIBRATION",
    "PEDAGOGY",
    "LEARNING_MODEL",
    "STUDENT_ADAPTATION",
    "CONCEPT_TEACHING",
    "EXECUTION",
]

DOMAIN_SECTION_NAMES = {
    "DSA_MODE",
    "SYSTEM_DESIGN_MODE",
    "MOCK_INTERVIEW_MODE",
    "MOCK_GOOGLE",
    "MOCK_META",
    "MOCK_AMAZON",
    "MOCK_MICROSOFT",
    "MOCK_GENERIC",
}

MODE_TOOLS: dict[SessionMode, dict] = {
    SessionMode.GENERAL: {
        "enable": [],
        "disable": ["run_code", "push_code", "draw_on_canvas"],
    },
    SessionMode.DSA: {
        "enable": ["run_code", "push_code"],
        "disable": ["draw_on_canvas"],
    },
    SessionMode.SYSTEM_DESIGN: {
        "enable": ["draw_on_canvas"],
        "disable": ["run_code", "push_code"],
    },
    SessionMode.MOCK_INTERVIEW: {
        "enable": ["run_code"],
        "disable": ["push_code", "draw_on_canvas"],
    },
}

MODE_UI: dict[SessionMode, UILayout] = {
    SessionMode.GENERAL: UILayout.BOARD,
    SessionMode.DSA: UILayout.BOARD_EDITOR,
    SessionMode.SYSTEM_DESIGN: UILayout.BOARD_CANVAS,
    SessionMode.MOCK_INTERVIEW: UILayout.BOARD_EDITOR,
}


@dataclass
class SessionBlueprint:
    mode: str = "general"
    interaction: str = "study"
    ui_layout: str = "board"
    prompt_sections: list[str] = field(default_factory=lambda: list(CORE_SECTIONS))
    tools_enable: list[str] = field(default_factory=list)
    tools_disable: list[str] = field(default_factory=list)
    problem_slug: str | None = None
    mock_company: str = "generic"
    mock_timer_minutes: int = 45
    frozen_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "interaction": self.interaction,
            "ui_layout": self.ui_layout,
            "prompt_sections": self.prompt_sections,
            "tools_enable": self.tools_enable,
            "tools_disable": self.tools_disable,
            "problem_slug": self.problem_slug,
            "mock_company": self.mock_company,
            "mock_timer_minutes": self.mock_timer_minutes,
            "frozen_at": self.frozen_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SessionBlueprint:
        if not d:
            return cls()
        return cls(
            mode=d.get("mode", "general"),
            interaction=d.get("interaction", "study"),
            ui_layout=d.get("ui_layout", "board"),
            prompt_sections=d.get("prompt_sections", list(CORE_SECTIONS)),
            tools_enable=d.get("tools_enable", []),
            tools_disable=d.get("tools_disable", []),
            problem_slug=d.get("problem_slug"),
            mock_company=d.get("mock_company", "generic"),
            mock_timer_minutes=d.get("mock_timer_minutes", 45),
            frozen_at=d.get("frozen_at", time.time()),
        )


# ═══════════════════════════════════════════════════════════
# Haiku Classifier
# ═══════════════════════════════════════════════════════════

_CLASSIFIER_PROMPT = """You are a session classifier for an AI tutoring platform called Euler.
Given the student's input text, classify it into the correct session configuration.

The platform supports:
1. **general** — Any academic subject: physics, math, chemistry, biology, business, history, literature, etc. This is the DEFAULT for anything that is not specifically DSA, system design, or mock interview.
2. **dsa** — Data structures & algorithms: coding problems, LeetCode/NeetCode problems, algorithm techniques (DP, BFS, DFS, binary search, two pointers, sliding window, etc.), data structure operations (arrays, linked lists, trees, graphs, heaps, stacks, queues, tries, hash maps).
3. **sd** — System design: designing distributed systems, architecture, scalability, load balancing, caching, sharding, databases, microservices, API design. Specific systems like "design Uber", "design a URL shortener".
4. **mock_interview** — Mock technical interview simulation: when the student explicitly wants to practice an interview scenario with timer and evaluation.

Rules:
- Default to "general" unless the input is clearly about DSA, system design, or mock interviews.
- "tree" alone is general (could be biology). "binary tree traversal" is DSA.
- "graph my data" is general. "graph traversal algorithm" is DSA.
- "design a poster" is general. "design a distributed cache" is SD.
- "mock exam" is general. "mock interview" is mock_interview.
- If mock_interview, detect the company if mentioned: google, meta, amazon, microsoft. Default to "generic".
- For interaction: "study" if student wants to learn/understand/be taught. "practice" if they want to solve/code/work independently.

Respond with ONLY a JSON object, no other text:
{"mode": "general|dsa|sd|mock_interview", "interaction": "study|practice", "company": "generic|google|meta|amazon|microsoft"}"""


async def _classify_with_haiku(text: str) -> dict:
    """Call Haiku to classify the student's intent. Returns parsed JSON."""
    try:
        from app.core.llm import llm_call
        from app.core.config import settings

        response = await llm_call(
            model=settings.MODEL_FAST,
            system=_CLASSIFIER_PROMPT,
            messages=[{"role": "user", "content": text}],
            max_tokens=100,
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = json.loads(raw)
        log.info("Haiku classified '%s' → %s", text[:60], result)
        return result
    except Exception as e:
        log.warning("Haiku classification failed for '%s': %s — falling back to general", text[:60], e)
        return {"mode": "general", "interaction": "study", "company": "generic"}


def _classify_sync_fallback(text: str) -> dict:
    """Synchronous fallback when event loop isn't available (testing)."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Can't await in a running loop — return general as safe default
        log.warning("Cannot run async classifier in sync context — defaulting to general")
        return {"mode": "general", "interaction": "study", "company": "generic"}

    return asyncio.run(_classify_with_haiku(text))


# ═══════════════════════════════════════════════════════════
# Blueprint Factory
# ═══════════════════════════════════════════════════════════


def _build_from_mode(
    mode: SessionMode,
    interaction: Interaction,
    company: str = "generic",
    slug: str | None = None,
    timer: int = 45,
) -> SessionBlueprint:
    """Build a blueprint from a known mode (no classification needed)."""
    sections = list(CORE_SECTIONS)

    if mode == SessionMode.DSA:
        sections.append("DSA_MODE")
    elif mode == SessionMode.SYSTEM_DESIGN:
        sections.append("SYSTEM_DESIGN_MODE")
    elif mode == SessionMode.MOCK_INTERVIEW:
        sections.append("MOCK_INTERVIEW_MODE")
        company_section = f"MOCK_{company.upper()}"
        if company_section in DOMAIN_SECTION_NAMES:
            sections.append(company_section)

    tool_cfg = MODE_TOOLS.get(mode, MODE_TOOLS[SessionMode.GENERAL])
    ui = MODE_UI.get(mode, UILayout.BOARD)

    return SessionBlueprint(
        mode=mode.value,
        interaction=interaction.value,
        ui_layout=ui.value,
        prompt_sections=sections,
        tools_enable=list(tool_cfg["enable"]),
        tools_disable=list(tool_cfg["disable"]),
        problem_slug=slug,
        mock_company=company if mode == SessionMode.MOCK_INTERVIEW else "generic",
        mock_timer_minutes=timer,
        frozen_at=time.time(),
    )


async def classify_intent(
    text: str,
    explicit_mode: str | None = None,
    explicit_interaction: str | None = None,
    explicit_slug: str | None = None,
    explicit_company: str | None = None,
    explicit_timer: int | None = None,
) -> SessionBlueprint:
    """Classify student intent into a SessionBlueprint.

    Fast path: if explicit_mode is set (from UI buttons/links), skip Haiku.
    Slow path: call Haiku to classify freeform text input.
    """
    # ── Fast path: explicit mode from UI ──
    if explicit_mode:
        try:
            mode = SessionMode(explicit_mode)
        except ValueError:
            mode = SessionMode.GENERAL

        if explicit_interaction:
            interaction = Interaction(explicit_interaction) if explicit_interaction in ("study", "practice") else Interaction.STUDY
        elif explicit_slug and mode in (SessionMode.DSA, SessionMode.SYSTEM_DESIGN):
            interaction = Interaction.PRACTICE
        else:
            interaction = Interaction.STUDY

        return _build_from_mode(
            mode=mode,
            interaction=interaction,
            company=explicit_company or "generic",
            slug=explicit_slug,
            timer=explicit_timer or 45,
        )

    # ── Slow path: classify freeform text with Haiku ──
    if not text or not text.strip():
        return _build_from_mode(SessionMode.GENERAL, Interaction.STUDY)

    result = await _classify_with_haiku(text)

    try:
        mode = SessionMode(result.get("mode", "general"))
    except ValueError:
        mode = SessionMode.GENERAL

    try:
        interaction = Interaction(result.get("interaction", "study"))
    except ValueError:
        interaction = Interaction.STUDY

    company = result.get("company", "generic") or "generic"

    return _build_from_mode(
        mode=mode,
        interaction=interaction,
        company=company,
        slug=explicit_slug,
        timer=explicit_timer or 45,
    )


def classify_intent_sync(
    text: str,
    explicit_mode: str | None = None,
    explicit_interaction: str | None = None,
    explicit_slug: str | None = None,
    explicit_company: str | None = None,
    explicit_timer: int | None = None,
) -> SessionBlueprint:
    """Synchronous wrapper for classify_intent (for non-async contexts)."""
    import asyncio

    return asyncio.run(classify_intent(
        text=text,
        explicit_mode=explicit_mode,
        explicit_interaction=explicit_interaction,
        explicit_slug=explicit_slug,
        explicit_company=explicit_company,
        explicit_timer=explicit_timer,
    ))
