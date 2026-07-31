"""Local deterministic AI provider — the zero-key offline engine.

When no external API keys are configured, this provider keeps the whole
platform functional end-to-end:

* Book brief / blueprint / chapter generation (structured JSON + real prose)
* Proofreading suggestions (deterministic language heuristics)
* Marketing copy (template-based, topic-aware)
* Cover design briefs (template-based)
* Assistant chat / edit actions (deterministic transforms)
* Translation via the free LibreTranslate public endpoint (no key)

It is clearly labelled as the "Local engine" in the UI and is always the last
fallback, so real LLMs take over the moment a key is configured.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from providers.ai.base import (
    AIProvider,
    AIResponse,
    ModelCapability,
    ProviderConfigurationError,
    TokenUsage,
)

# ---------------------------------------------------------------------------
# Small language-name -> code map for LibreTranslate
# ---------------------------------------------------------------------------
_LANG_CODES = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de",
    "portuguese": "pt", "italian": "it", "dutch": "nl", "japanese": "ja",
    "chinese": "zh", "russian": "ru", "arabic": "ar", "hindi": "hi",
    "korean": "ko", "polish": "pl", "turkish": "tr", "ukrainian": "uk",
}

_FILLERS = {
    "very", "really", "quite", "just", "basically", "actually",
    "literally", "kind of", "sort of", "a lot of",
}


def _extract(text: str, label: str, fallback: str = "") -> str:
    """Extract 'Label: value' from a prompt (value ends at the next label or blank line)."""
    pattern = re.compile(
        rf"(?:^|\n)\s*{re.escape(label)}\s*:\s*(.+?)(?=\n\s*[A-Z][A-Za-z ]+:|$)",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return fallback
    return match.group(1).strip()


def _extract_int(text: str, *labels: str, fallback: int) -> int:
    for label in labels:
        value = _extract(text, label)
        if not value:
            continue
        found = re.search(r"\d[\d,]*", value)
        if found:
            return int(found.group(0).replace(",", ""))
    return fallback


def _topic_words(text: str, limit: int = 5) -> list[str]:
    words = [w for w in re.split(r"[^A-Za-z0-9' -]+", text) if len(w) > 4]
    seen: list[str] = []
    for word in words:
        lowered = word.lower()
        if lowered in {"about", "book", "chapter", "audience", "this", "that", "with"}:
            continue
        if lowered not in seen:
            seen.append(lowered)
        if len(seen) >= limit:
            break
    return [w.title() for w in seen]


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


# ---------------------------------------------------------------------------
# Deterministic prose
# ---------------------------------------------------------------------------
_INTRO_TEMPLATES = [
    "This chapter explores {topic} through a practical, reader-first lens. "
    "By the end, you will understand why it matters for {audience} and how to "
    "apply it immediately.",
    "Every strong book on {topic} starts with a clear map. Here we lay out the "
    "foundations that the rest of the book builds on, always keeping {audience} "
    "in mind.",
    "Before we dive into tactics, it helps to be precise about what we mean by "
    "{topic}. This chapter defines the terms, sets expectations, and shows how "
    "the ideas connect.",
]

_BODY_TEMPLATES = [
    "One of the most useful ways to approach {topic} is to start small. Pick a "
    "single situation from your own experience, apply the principle, and note "
    "what changes. Most readers of {audience} find that this single habit "
    "produces faster results than any amount of theory.",
    "Consider the underlying mechanism. When you understand *why* something "
    "works, you stop memorising rules and start making better decisions on your "
    "own. The examples in this book are chosen to make that mechanism visible.",
    "A common mistake is to treat {topic} as a set of disconnected tricks. In "
    "practice, the pieces reinforce each other: clarity in one area creates "
    "confidence in the next, which in turn makes the whole system easier to "
    "maintain over time.",
    "Here is a concrete way to test this idea today. Write down one situation "
    "where the principle applies, decide on the smallest next action, and set a "
    "specific time to do it. Repetition with feedback is what turns knowledge "
    "into skill.",
    "It is also worth addressing the objections you might have. 'This sounds "
    "simple,' you may think — and that is exactly the point. The most durable "
    "approaches to {topic} are simple enough to practise daily and deep enough "
    "to keep improving for years.",
    "When you compare this with the alternative, the difference becomes clear. "
    "The default path is vague and reactive; the approach described here is "
    "specific, measurable, and designed around the realities of {audience}.",
]

_EXAMPLE_TEMPLATES = [
    "For example, imagine a reader who has just started with {topic}. Instead of "
    "trying to do everything at once, they focus on one principle, apply it for "
    "a week, and reflect on the outcome. That single loop builds momentum far "
    "more reliably than a perfect plan that is never executed.",
    "A realistic example: an author working on {topic} blocks out thirty minutes "
    "each morning, uses the checklist from the previous section, and reviews the "
    "result before moving on. Within a month the process stops feeling foreign "
    "and starts feeling natural.",
]

_TAKEAWAY_TEMPLATE = "**Key takeaway:** {point}"


def _render_paragraph(template: str, topic: str, audience: str, style: str) -> str:
    return template.format(topic=topic, audience=audience, style=style)


def _sections_for(topic: str, chapter_number: int) -> list[str]:
    pools = [
        ["Understanding the basics", "Why this matters", "How to apply it"],
        ["Setting clear goals", "Avoiding common mistakes", "Building the habit"],
        ["The core principles", "Practical techniques", "Tools that help"],
        ["Deepening your understanding", "Exercises and practice", "Reviewing progress"],
    ]
    return pools[chapter_number % len(pools)]


def _chapter_markdown(user_prompt: str) -> str:
    book_title = _extract(user_prompt, "Book", "The book")
    chapter_label = _extract(user_prompt, "Chapter")
    if chapter_label and ":" in chapter_label:
        chapter_number, chapter_title = chapter_label.split(":", 1)
        chapter_number = chapter_number.strip()
        chapter_title = chapter_title.strip()
    else:
        chapter_number = _extract_int(user_prompt, "Chapter", fallback=1)
        chapter_title = chapter_label or "Foundations"
    purpose = _extract(user_prompt, "Purpose", "")
    objective = _extract(user_prompt, "Objective", purpose)
    target = _extract_int(user_prompt, "Target word count", "word count", fallback=1000)
    target = max(350, min(target, 2500))
    audience = _extract(user_prompt, "Target audience", "readers")
    style = _extract(user_prompt, "Style guidance", "clear and practical")
    topic = (purpose or objective or book_title).strip() or "this subject"

    outline_block = ""
    outline_match = re.search(r"CHAPTER OUTLINE:\s*(.*?)(?=\n\n[A-Z]|$)", user_prompt, re.DOTALL)
    if outline_match:
        raw = outline_match.group(1)
        outline_block = "\n".join(
            line.strip().lstrip("-•*#").strip()
            for line in raw.splitlines()
            if line.strip()
        )
    section_titles = [line for line in outline_block.splitlines() if line][:6] or _sections_for(topic, int(chapter_number or 1))

    parts: list[str] = [f"# {chapter_title}"]
    intro_t = _INTRO_TEMPLATES[int(chapter_number or 1) % len(_INTRO_TEMPLATES)]
    parts.append(_render_paragraph(intro_t, topic, audience, style))

    block_index = 0
    for section in section_titles:
        parts.append(f"## {section}")
        for _ in range(2):
            template = _BODY_TEMPLATES[block_index % len(_BODY_TEMPLATES)]
            parts.append(_render_paragraph(template, topic, audience, style))
            block_index += 1
        if block_index % 3 == 0:
            example = _EXAMPLE_TEMPLATES[block_index % len(_EXAMPLE_TEMPLATES)]
            parts.append(_render_paragraph(example, topic, audience, style))
            block_index += 1
        if block_index % 2 == 0:
            parts.append("- A quick checklist item you can apply today.")
            parts.append("- A second checkpoint to verify your progress.")

    # Pad to the requested length (deterministic rotation of templates).
    while _word_count("\n".join(parts)) < int(target * 0.85) and block_index < 40:
        template = _BODY_TEMPLATES[block_index % len(_BODY_TEMPLATES)]
        parts.append(_render_paragraph(template, topic, audience, style))
        block_index += 1

    point = (
        purpose[:80] if purpose else
        f"The practical steps in this chapter move {audience} measurably closer to mastery of {topic}."
    )
    parts.append(_TAKEAWAY_TEMPLATE.format(point=point))
    parts.append(
        f"In the next chapter we build on this foundation, turning {topic} into "
        "a repeatable process you can rely on."
    )
    return "\n\n".join(parts)


def _blueprint(user_prompt: str) -> dict[str, Any]:
    topic = _extract(user_prompt, "Topic", _extract(user_prompt, "Title", "the book topic"))
    count = _extract_int(user_prompt, "Estimated chapter count", "chapter count", fallback=8)
    count = max(3, min(count, 25))
    total_words = _extract_int(user_prompt, "Estimated word count", "word count", fallback=10000)
    titles = (
        ["Introduction: Why This Book", "Foundations of the Topic", "Core Principles",
         "Common Mistakes and How to Avoid Them", "Practical Strategies That Work",
         "Tools, Resources, and Next Steps", "Building a Personal Action Plan",
         "Advanced Techniques", "Real-World Examples and Case Studies",
         "Measuring Progress and Staying on Track", "Conclusion: Your Road Ahead"]
    )
    if count <= 4:
        titles = titles[: count - 1] + ["Conclusion: Bringing It Together"]
    chapters: list[dict[str, Any]] = []
    for index in range(count):
        title = titles[index % len(titles)]
        if index == 0:
            title = f"Introduction: {topic}"
        elif index == count - 1:
            title = f"Conclusion: {topic} in Practice"
        chapters.append({
            "title": title,
            "objective": (
                f"Give the reader a clear, practical understanding of '{title}' "
                f"as it relates to {topic}, with concrete steps they can apply."
            ),
            "summary": f"This chapter covers the essentials of {title} for {topic}, "
                       "with examples, common pitfalls, and actionable takeaways.",
            "key_lessons": [
                f"The single most important idea in {title}",
                "How to avoid the typical beginner mistakes",
                "A repeatable routine for applying what you learned",
            ],
            "important_examples": [
                f"A worked example: applying {title} to a realistic {topic} situation",
                f"A before/after comparison showing the impact of {title}",
            ],
        })
    return {
        "introduction_purpose": (
            f"Set the stage for {topic}: why it matters, who this book is for, "
            "what the reader will be able to do by the end, and how the chapters fit together."
        ),
        "chapters": chapters,
        "estimated_total_word_count": total_words,
    }


def _brief(user_prompt: str) -> dict[str, Any]:
    title = _extract(user_prompt, "Title", "Untitled book")
    subtitle = _extract(user_prompt, "Subtitle", "")
    description = _extract(user_prompt, "Description", "")
    audience = _extract(user_prompt, "Target audience", "general readers")
    tone = _extract(user_prompt, "Tone", "conversational")
    style = _extract(user_prompt, "Writing style", "practical")
    words = _extract_int(user_prompt, "Approximate length", "word count", fallback=10000)
    themes = _topic_words(f"{title} {description}", 5)
    return {
        "working_title": title,
        "subtitle": subtitle,
        "book_purpose": (
            f"Help {audience} master {description or title} through clear explanations, "
            "practical examples, and a structured path from first principles to confident application."
        ),
        "target_reader": audience,
        "reader_problems": [
            f"{audience.title()} lacks a clear, structured starting point for {description or title}",
            "Information overload from scattered advice and no repeatable method",
            "Difficulty turning knowledge into consistent daily practice",
        ],
        "promised_transformation": (
            f"By the end of this book, {audience} will have a repeatable system "
            f"for {description or title} — and the confidence to apply it."
        ),
        "tone": tone,
        "writing_style": style,
        "key_themes": themes or ["Practical application", "Consistent practice", "Clear frameworks"],
        "major_concepts": [f"Core framework for {description or title}", "Common pitfalls", "Action routines"],
        "topics_to_avoid": ["Unnecessary jargon", "Unverified claims", "Overly dense theory without examples"],
        "suggested_structure": "Introduction, followed by progressive chapters that build skill step by step, ending with a practical action plan.",
        "estimated_chapter_count": 5 if words <= 5000 else 8 if words <= 10000 else 10 if words <= 15000 else 14 if words <= 25000 else 20,
        "estimated_word_count": words,
    }


def _proofread_suggestions(text: str) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    # Long sentences
    for match in re.finditer(r"[^.!?]+[.!?]", text):
        sentence = match.group(0).strip()
        if _word_count(sentence) > 45 and len(suggestions) < 8:
            suggestions.append({
                "category": "clarity", "severity": "medium", "confidence": 0.7,
                "original_text": sentence,
                "suggested_text": None,
                "explanation": (
                    f"This sentence is {_word_count(sentence)} words long. Consider splitting "
                    "it into two or three shorter sentences to improve readability."
                ),
            })
    # Passive voice
    for match in re.finditer(r"\b(?:is|are|was|were|been|being)\s+\w+ed\b", text):
        if len(suggestions) < 8:
            suggestions.append({
                "category": "style", "severity": "low", "confidence": 0.6,
                "original_text": match.group(0),
                "suggested_text": None,
                "explanation": "Passive construction. Consider rewriting with an active subject for a stronger sentence.",
            })
    # Filler words
    for word in _FILLERS:
        if len(suggestions) >= 8:
            break
        for match in re.finditer(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            if len(suggestions) >= 8:
                break
            suggestions.append({
                "category": "style", "severity": "low", "confidence": 0.8,
                "original_text": match.group(0),
                "suggested_text": None,
                "explanation": f"Filler word '{word}' usually weakens the sentence. Removing it tightens the prose.",
            })
    # Repeated words
    for match in re.finditer(r"\b(\w{4,})\b\s+\1\b", text, re.IGNORECASE):
        if len(suggestions) >= 8:
            break
        suggestions.append({
            "category": "repetition", "severity": "low", "confidence": 0.75,
            "original_text": match.group(0),
            "suggested_text": match.group(1),
            "explanation": f"'{match.group(1)}' is repeated back-to-back. Remove the duplicate.",
        })
    # Double spaces / spacing
    for match in re.finditer(r"  +", text):
        if len(suggestions) >= 8:
            break
        suggestions.append({
            "category": "punctuation", "severity": "low", "confidence": 0.9,
            "original_text": match.group(0),
            "suggested_text": " ",
            "explanation": "Multiple spaces found. Replace with a single space.",
        })
    return suggestions


def _marketing_asset(user_prompt: str) -> str:
    title = _extract(user_prompt, "Book Title", "This book")
    subtitle = _extract(user_prompt, "Subtitle", "")
    audience = _extract(user_prompt, "Target Audience", "readers")
    description = _extract(user_prompt, "Description", title)
    label_match = re.search(r"Generate a high-quality (.+?) for this book", user_prompt)
    label = label_match.group(1).strip() if label_match else "marketing copy"

    if "description" in label.lower() or "amazon" in label.lower():
        return (
            f"{title}{': ' + subtitle if subtitle else ''}\n\n"
            f"{description} Written specifically for {audience}, this book turns "
            f"clear principles into a practical, repeatable system. Each chapter "
            f"ends with concrete actions, so readers finish with a plan — not just "
            f"good intentions.\n\n"
            f"What you will learn:\n"
            f"- The core ideas behind {title}, explained without jargon\n"
            f"- A step-by-step routine you can start today\n"
            f"- Common mistakes and how to avoid them\n\n"
            f"Scroll up, click Buy Now, and start building your {label} today."
        )
    if "keyword" in label.lower():
        return ", ".join(_topic_words(f"{title} {description}", 10)) or "ebook, guide, practical"
    if "subtitle" in label.lower():
        return (
            f"Practical steps to master {description or title} — "
            f"a friendly, action-oriented guide for {audience}."
        )
    if "email" in label.lower():
        return (
            f"Subject: Your {title} journey starts here\n\n"
            f"Hi there,\n\nYou are reading this because {description or title} matters to you. "
            f"This book gives {audience} a clear, friendly path — with exercises at the "
            f"end of every chapter. Reply to this email with any questions. Happy reading!"
        )
    return (
        f"{title} — {description}\n"
        f"Built for {audience}. Clear steps. Real results. Pick up your copy today."
    )


def _cover_brief(user_prompt: str) -> str:
    title = _extract(user_prompt, "title placement", _extract(user_prompt, "Book Title", "The book"))
    title = title.replace('"', "").strip()
    subtitle = _extract(user_prompt, "subtitle placement", "").replace('"', "").strip()
    author = _extract(user_prompt, "author name", "Author").replace('"', "").strip()
    if "BACK COVER" in user_prompt:
        description = _extract(user_prompt, "Description", title)
        return (
            "Back cover design brief\n"
            "1. Blurb: " + description[:400] + " — a practical, encouraging description of the book.\n"
            "2. Author bio: A short, warm bio positioning the author as a trusted guide for the reader.\n"
            "3. Layout: Blurb on the left, author bio below, barcode/ISBN placeholder in the bottom-right corner.\n"
            "4. Palette: Matches the front cover; calm, professional tones with high contrast for the blurb."
        )
    if "SPINE" in user_prompt:
        return (
            "Spine design brief\n"
            "1. Text layout: Title top-to-bottom (reading direction), author name top-to-bottom below it.\n"
            "2. Width: Standard trade spine; keep text 20% smaller than the cover title.\n"
            "3. Publisher logo: Small, bottom third of the spine.\n"
            "4. Color: Same background as the front cover for a continuous look."
        )
    return (
        "Front cover design brief\n"
        f"1. Concept: A clean, memorable visual that signals '{subtitle or 'a practical guide'}' — "
        "one strong central image with generous negative space.\n"
        f"2. Palette: 3-5 colors — a primary accent, a neutral background, and two supporting tones.\n"
        "3. Typography: Bold serif or geometric sans for the title; light sans for the subtitle.\n"
        f"4. Key elements: Title '{title}' centered or upper-third; subtitle below; author '{author}' at the bottom.\n"
        "5. Layout: Balanced thirds composition, safe margins for trim, no text closer than 0.5in to the edge."
    )


def _assistant_edit(user_prompt: str, action: str) -> str:
    match = re.search(r"<<<(.*?)>>>", user_prompt, re.DOTALL)
    content = match.group(1).strip() if match else ""
    if not content:
        raise ProviderConfigurationError(
            "The assistant could not find chapter content to edit. Select a chapter and retry.",
            provider="local",
        )
    action = action.lower()
    if action == "fix_grammar":
        fixes = {
            r"\bteh\b": "the", r"\brecieve\b": "receive", r"\bseperate\b": "separate",
            r"\bdefinately\b": "definitely", r"\boccured\b": "occurred",
            r"\bwich\b": "which", r"\btherefor\b": "therefore", r"\buntill\b": "until",
        }
        result = content
        for pattern, replacement in fixes.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        result = re.sub(r"  +", " ", result)
        return result
    if action == "shorten":
        sentences = re.findall(r"[^.!?]+[.!?]", content)
        kept = sentences[: max(1, int(len(sentences) * 0.7))]
        return " ".join(kept).strip()
    if action == "expand":
        topic = _topic_words(content, 1)
        extra = (
            "\n\nLet us look at this from another angle. When readers first meet these ideas, "
            "they often focus on the *what* and skip the *why*. That is a mistake: understanding "
            "the reasoning behind the approach makes it far easier to adapt when circumstances "
            "change. Take a few minutes to write down how this principle applies to your own "
            "situation — specificity turns advice into action.\n\n"
            "You may also find it useful to pair this chapter with the exercises at the end of "
            "the book. Each exercise is designed to be finished in ten minutes or less, so "
            "consistency beats intensity. Revisit your answers a week later and you will notice "
            "how much your thinking has sharpened."
        )
        return content + extra
    if action == "continue":
        continuation = (
            "\n\nBuilding on what we have covered, the next step is to make the approach your "
            "own. Experiment with the techniques in this chapter, keep what works, and adjust "
            "what does not. Most readers find that a two-week trial period is enough to see "
            "clear progress — after that, the habit becomes part of the routine rather than "
            "something you have to remember.\n\n"
            "Before moving on, take stock: which single idea from this chapter will you apply "
            "today? Write it down, act on it, and come back to this book with the result. "
            "That feedback loop is what transforms reading into mastery."
        )
        return content + continuation
    if action == "rewrite":
        # Re-emit the same ideas with a fresh structure: keep headings, re-order bodies.
        blocks = [b.strip() for b in re.split(r"\n\s*\n", content) if b.strip()]
        if len(blocks) > 2:
            head, body, tail = blocks[0], blocks[1:-1], blocks[-1]
            reordered = body[1:] + body[:1]
            return "\n\n".join([head, *reordered, tail])
        return content
    raise ProviderConfigurationError(f"Unknown edit action '{action}'.", provider="local")


class LocalProvider(AIProvider):
    """Deterministic offline provider — always available, last in fallback order."""

    PROVIDER = "local"
    DISPLAY_NAME = "Local engine (offline)"

    SUPPORTED = {
        ModelCapability.TEXT_GENERATION,
        ModelCapability.STRUCTURED_OUTPUT,
        ModelCapability.STREAMING,
    }

    @property
    def name(self) -> str:
        return self.PROVIDER

    @property
    def display_name(self) -> str:
        return self.DISPLAY_NAME

    def validate_configuration(self) -> None:
        return None  # Always configured.

    async def health_check(self) -> bool:
        return True

    async def get_available_models(self) -> list[str]:
        return ["local/general", "local/book-writer"]

    # ------------------------------------------------------------------
    def _prompt_text(self, request: Any) -> tuple[str, str]:
        system = request.system_prompt or ""
        user = "\n".join(m.content for m in request.messages)
        return system, user

    async def _translate(self, system: str, user: str) -> str:
        match = re.search(r"from\s+([A-Za-z]+)\s+to\s+([A-Za-z]+)", system, re.IGNORECASE)
        if not match:
            raise ProviderConfigurationError(
                "The local engine could not determine the translation languages. "
                "Configure an AI provider key to translate this book.",
                provider=self.PROVIDER,
            )
        source_name, target_name = match.group(1).lower(), match.group(2).lower()
        source = _LANG_CODES.get(source_name, source_name[:2])
        target = _LANG_CODES.get(target_name, target_name[:2])
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://libretranslate.com/translate",
                    json={"q": user, "source": source, "target": target, "format": "text"},
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise ProviderConfigurationError(
                "The free LibreTranslate service is unreachable right now. "
                "Configure an AI provider key (Settings → AI) to translate this book.",
                provider=self.PROVIDER,
                retryable=True,
            ) from exc
        translated = data.get("translatedText", "")
        if not translated:
            raise ProviderConfigurationError(
                "Translation returned an empty result. Try again or configure an AI provider key.",
                provider=self.PROVIDER,
            )
        return translated

    # ------------------------------------------------------------------
    async def generate_text(self, request: Any) -> AIResponse:
        system, user = self._prompt_text(request)
        lower_system = system.lower()

        if "translate" in lower_system:
            text = await self._translate(system, user)
        elif "action:" in lower_system:
            action_match = re.search(r"ACTION:\s*(\w+)", system, re.IGNORECASE)
            action = action_match.group(1) if action_match else "chat"
            text = _assistant_edit(user, action)
        elif "assistant inside ai ebook studio" in lower_system:
            question = _extract(user, "QUESTION", "Help me with my book")
            topic = _topic_words(user, 2)
            text = (
                f"Here is my take on that.\n\n"
                f"Focus on the reader's outcome: {question}\n\n"
                f"Three concrete suggestions for your current chapter:\n"
                f"1. Open with the problem your reader feels most strongly about — "
                f"it hooks attention faster than an abstract introduction.\n"
                f"2. Add one worked example per section (real numbers, real steps). "
                f"Readers of this book learn by doing.\n"
                f"3. End the chapter with a single 'do this now' action and a "
                f"transition to the next chapter.\n\n"
                f"Want me to rewrite, expand, shorten, or fix grammar in the current "
                f"chapter? Use the quick actions above the editor."
            )
        elif "cover" in lower_system or "design the" in lower_system:
            text = _cover_brief(user)
        elif "high-quality" in lower_system or "marketing" in lower_system:
            text = _marketing_asset(user)
        else:
            topic = _topic_words(user, 2)
            text = (
                f"Here is a practical take on \"{user[:140]}\".\n\n"
                f"Start from the reader's situation: what do they know, what do they "
                f"need, and what is the smallest next step? For {' and '.join(topic) or 'this topic'}, "
                f"a concrete example beats abstract advice every time. Structure the answer as: "
                f"insight, example, action — then invite the reader to apply it before moving on."
            )
        return AIResponse(
            content=text,
            provider=self.PROVIDER,
            model="local/general",
            usage=TokenUsage(input_tokens=0, output_tokens=_word_count(text), total_tokens=0),
        )

    # ------------------------------------------------------------------
    async def generate_structured_output(self, request: Any, schema: dict[str, Any]) -> dict[str, Any]:
        system, user = self._prompt_text(request)
        properties = (schema or {}).get("properties") or {}

        if "content" in properties and set(properties.keys()) <= {"content"}:
            return {"content": _chapter_markdown(user)}
        if "working_title" in properties:
            return _brief(user)
        if "introduction_purpose" in properties:
            return _blueprint(user)
        if "suggestions" in properties:
            return {"suggestions": _proofread_suggestions(user)}
        if "chapters" in properties and "estimated_total_word_count" in properties:
            return _blueprint(user)

        # Generic best-effort fill so callers always get schema-shaped output.
        result: dict[str, Any] = {}
        for key, prop in properties.items():
            prop_type = prop.get("type", "string")
            if prop_type == "array":
                result[key] = []
            elif prop_type in ("integer", "number"):
                result[key] = _extract_int(user, key, fallback=0)
            elif prop_type == "boolean":
                result[key] = False
            elif prop_type == "object":
                result[key] = {}
            else:
                result[key] = _extract(user, key, "")
        for key in (schema or {}).get("required", []):
            result.setdefault(key, "" if properties.get(key, {}).get("type") != "array" else [])
        return result

    # ------------------------------------------------------------------
    async def stream_text(self, request: Any) -> AsyncIterator[str]:
        response = await self.generate_text(request)
        yield response.content
