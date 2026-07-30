"""Prompt engine for template rendering, versioned prompts, and variable injection.

Example::

    engine = PromptEngine()
    prompt = engine.render("$system", user_name="Ada")
    result = engine.render("write_chapter", book_genre="sci-fi", chapter=1)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from string import Template
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# --- built-in default prompts ---

_DEFAULT_SYSTEM = (
    "You are an expert assistant for an AI-powered ebook writing studio. "
    "Be concise, accurate, and helpful."
)

_DEFAULT_USER = "Please assist with the following: {user_message}"


class PromptEngineError(Exception):
    """Raised when a template or prompt operation fails."""


@dataclass(frozen=True)
class PromptVersion:
    """A specific version of a prompt with immutable metadata."""

    version: str  # e.g. "1.2.0"
    content: str
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class PromptTemplate:
    """A named, versioned prompt template."""

    name: str
    default_version: str = "1.0.0"
    system: str | None = None
    user: str | None = None
    variables: tuple[str, ...] = field(default_factory=tuple)
    created_at: float = field(default_factory=time.time)
    __prompt_registry: dict[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        # Ensure name is valid identifier-like
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", self.name):
            raise PromptEngineError(f"Invalid prompt name '{self.name}'. Must be identifier-like.")

    def get_prompt(self, version: str | None = None) -> str:
        "Return the prompt string for a specific version (or default)."
        version = version or self.default_version
        prompt = self.__prompt_registry.get(version)
        if prompt is None:
            raise PromptEngineError(f"Version '{version}' not found for prompt '{self.name}'.")
        return prompt

    def register_version(self, version: str, content: str) -> PromptTemplate:
        "Register a new version of this prompt."
        self.__prompt_registry[version] = content
        return self


class PromptEngine:
    """Template rendering engine with prompt versioning and variable substitution."""

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self._logger = structlog.get_logger(__name__)
        self._register_builtins()

    # ---- public API ----

    def register(  # noqa: PLR0913
        self,
        name: str,
        user: str | None = None,
        system: str | None = None,
        default_version: str = "1.0.0",
        variables: tuple[str, ...] = (),
    ) -> PromptTemplate:
        """Register a new prompt template."""
        template = PromptTemplate(
            name=name,
            system=system,
            user=user,
            default_version=default_version,
            variables=variables,
        )
        self._templates[name] = template
        self._logger.debug("prompt_registered", name=name, version=default_version)
        return template

    def render(self, prompt_name: str, /, **variables: Any) -> str:
        """Render a prompt by name, injecting variables."""
        if prompt_name not in self._templates:
            raise PromptEngineError(f"Prompt '{prompt_name}' not found.")
        template = self._templates[prompt_name]
        raw = template.get_prompt()
        return self._inject(raw, **variables)

    def build_messages(  # noqa: PLR0913
        self,
        *,
        system: str | None = None,
        user: str | None = None,
        context: dict[str, Any] | None = None,
        prompt_name: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Build (system, user) prompt strings from a named prompt or raw strings."""
        if prompt_name:
            if prompt_name not in self._templates:
                raise PromptEngineError(f"Prompt '{prompt_name}' not found.")
            template = self._templates[prompt_name]
            system_out = template.system
            user_out = template.user
        else:
            system_out = system
            user_out = user

        ctx = context or {}
        if system_out:
            system_out = self._inject(system_out, **ctx)
        if user_out:
            user_out = self._inject(user_out, **ctx)
        return system_out, user_out

    def list_templates(self) -> list[str]:
        """Return registered template names."""
        return list(self._templates.keys())

    def get_template(self, name: str) -> PromptTemplate | None:
        """Return a registered template by name."""
        return self._templates.get(name)

    # ---- internals ----

    def _register_builtins(self) -> None:
        self.register(
            "default",
            system=_DEFAULT_SYSTEM,
            user=_DEFAULT_USER,
            default_version="1.0.0",
            variables=("user_message",),
        )
        self._templates["default"].register_version("1.0.0", _DEFAULT_USER)

    @staticmethod
    def _inject(template: str, /, **kw: Any) -> str:
        # Safe substitution using both {var} and $var syntax
        try:
            # Try Python Template first ($var)
            t = Template(template)
            return t.substitute(**kw)
        except (KeyError, ValueError):
            # Fall back to simple .format replacement
            return template.format(**kw)
