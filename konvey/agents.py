"""Agno agent factories for the three Konvey roles.

- Agent 1 Knowledge Discovery: USER_PROMPT -> KNOWLEDGE_PACK (structured).
- Agent 2 Planning + Scene Generation: KNOWLEDGE_PACK -> 3-scene plan (structured).
- Agent 3 Stage Director: SCENE_SPEC (1 scene) -> beat HTML (plain text).

Instructions come verbatim from the repo's markdown prompts
(:mod:`konvey.prompts`) so prompt edits stay in ``prompts/``. Model is
configurable: pass any Agno ``Model`` (or ``"provider:id"`` string), or leave
``None`` to pick a provider from the environment / ``.env`` file:

- ``KONVEY_PROVIDER=opencode`` (default when ``OPENCODE_API_KEY`` is set):
  OpenCode Zen's OpenAI-compatible endpoint (``/chat/completions``).
- ``KONVEY_PROVIDER=opencode-go``: same, on the OpenCode Go subscription.
- ``KONVEY_PROVIDER=minimax``: MiniMax with ``MINIMAX_API_KEY``.
- ``KONVEY_PROVIDER=inception``: Inception Labs' OpenAI-compatible endpoint with
  ``INCEPTION_API_KEY`` (diffusion LLMs; ``INCEPTION_MODEL_ID``, default mercury-3).

Model id: ``OPENCODE_MODEL_ID`` (default glm-5.3 on Zen,
muse-spark-1.3-contributor on Go) for OpenCode,
``KONVEY_MODEL_ID`` (default MiniMax-M3) for MiniMax — kept separate because
the two providers spell ids differently (``minimax-m3`` vs ``MiniMax-M3``).
"""

from __future__ import annotations

import os
import uuid
from typing import Optional, Union

from agno.agent import Agent
from agno.models.google import Gemini
from agno.models.minimax import MiniMax
from agno.models.openai.like import OpenAILike
from agno.models.openai.open_responses import OpenResponses
from dotenv import load_dotenv

from .compute import ComputeLog, make_tools
from .prompts import PromptMode, build_agent_instructions
from .schemas import KnowledgePack, StagePlan

ModelLike = Union[str, object]  # str "provider:id" or agno Model instance

DEFAULT_MODEL_ID = "MiniMax-M3"

# OpenCode routes models to different wire formats. Supported here:
# - gemini-* -> Google generateContent (/models/<id>), via agno Gemini.
# - muse-*, gpt-*, grok-* -> OpenAI Responses API (/responses).
# - glm-*, kimi-*, deepseek-*, qwen3.8-max (and minimax-* on Zen)
#   -> OpenAI-compatible /chat/completions.
# - claude-* -> Anthropic Messages API (/messages), via agno Claude.
OPENCODE_BASE_URLS = {
    "opencode": "https://opencode.ai/inference/v1",
    "opencode-go": "https://opencode.ai/inference/go/v1",
}
OPENCODE_DEFAULT_MODEL_IDS = {
    "opencode": "glm-5.3",
    "opencode-go": "muse-spark-1.3-contributor",  # Go-only; prompts may train Meta models
}
OPENCODE_USER_AGENT = "konvey/0.1.0"
INCEPTION_BASE_URL = "https://api.inceptionlabs.ai/v1"
INCEPTION_DEFAULT_MODEL_ID = "mercury-3"
INCEPTION_EFFORT = "medium"
RESPONSES_API_PREFIXES = ("muse-", "gpt-", "grok-")
# Reasoning effort sent per model family (models.dev: haiku low..max, deepseek flash
# low/high/max). None: nothing is sent and each runs at its server default (haiku: medium),
# the user's choice since 2026-10-17 ("high" ran haiku's thinking into the token cap).
# KONVEY_EFFORT overrides for the families listed here.
REASONING_EFFORT: dict[str, Optional[str]] = {"claude-haiku-": None, "deepseek-": None}
# Agent 1 compute tools: enough to trace an example and a few series, not an endless loop.
MAX_TOOL_CALLS = 16


class ReasoningOpenAILike(OpenAILike):
    """OpenAILike that sends each assistant turn's reasoning_content back.

    DeepSeek's thinking mode rejects a tool-call turn without it ("The `reasoning_content` in the
    thinking mode must be passed back to the API"); agno's OpenAILike drops it (its own DeepSeek
    class keeps it, but does not speak OpenCode's endpoint).
    """

    def _format_message(self, message, compress_tool_results: bool = False):
        formatted = super()._format_message(message, compress_tool_results)
        if message.role == "assistant" and message.reasoning_content is not None:
            formatted["reasoning_content"] = message.reasoning_content
        return formatted


class InceptionChat(OpenAILike):
    """OpenAILike that waits out Inception's per-minute token limits.

    The 429 reads "output token limit exceeded", which agno takes for a context-window error
    ("token limit") and does not retry.
    """

    def _is_retryable_error(self, error) -> bool:
        return error.status_code == 429 or super()._is_retryable_error(error)


# Model families whose reasoning has to be resent with the next request.
RESEND_REASONING_PREFIXES = ("deepseek-",)


def default_provider() -> str:
    explicit = os.getenv("KONVEY_PROVIDER")
    if explicit:
        return explicit.strip().lower()
    return "opencode" if os.getenv("OPENCODE_API_KEY") else "minimax"


def reasoning_effort(model_id: str) -> Optional[str]:
    if not any(model_id.startswith(prefix) for prefix in REASONING_EFFORT):
        return None
    effort = next(e for prefix, e in REASONING_EFFORT.items() if model_id.startswith(prefix))
    return os.getenv("KONVEY_EFFORT") or effort


def model_id_env(provider: str) -> str:
    if provider == "inception":
        return "INCEPTION_MODEL_ID"
    return "OPENCODE_MODEL_ID" if provider in OPENCODE_BASE_URLS else "KONVEY_MODEL_ID"


def resolve_model(model: Optional[ModelLike] = None) -> Union[str, object]:
    if model is not None:
        return model
    load_dotenv()  # picks up .env (KONVEY_PROVIDER, *_API_KEY, KONVEY_MODEL_ID)
    provider = default_provider()
    if provider in OPENCODE_BASE_URLS:
        api_key = os.getenv("OPENCODE_API_KEY")
        if not api_key:
            raise RuntimeError(f"KONVEY_PROVIDER={provider} needs OPENCODE_API_KEY (get one at https://opencode.ai/auth)")
        model_id = os.getenv("OPENCODE_MODEL_ID", OPENCODE_DEFAULT_MODEL_IDS[provider])
        base_url = os.getenv("OPENCODE_BASE_URL", OPENCODE_BASE_URLS[provider])
        # OpenCode asks clients to name themselves and send one stable session
        # id per conversation (routing + prompt caching); each agent is one.
        headers = {"User-Agent": OPENCODE_USER_AGENT, "x-opencode-session": str(uuid.uuid4())}
        if model_id.startswith("gemini-"):
            # google-genai builds {base_url}/{api_version}/models/<id>:generateContent
            root, _, api_version = base_url.rstrip("/").rpartition("/")
            return Gemini(
                id=model_id,
                name="OpenCode",
                provider="OpenCode",
                api_key=api_key,
                client_params={"http_options": {"base_url": root + "/", "api_version": api_version, "headers": headers}},
                supports_native_structured_outputs=False,
            )
        if model_id.startswith("claude-"):
            # Anthropic Messages API: the SDK appends /v1/messages to the base URL.
            from agno.models.anthropic import Claude

            claude = Claude(
                id=model_id,
                name="OpenCode",
                provider="OpenCode",
                api_key=api_key,
                default_headers=headers,
                # An explicit timeout: with the SDK's default one it refuses a non-streaming request
                # whose max_tokens could run past 10 minutes (anything over ~21k).
                client_params={"base_url": base_url.rstrip("/").removesuffix("/v1"), "timeout": 900.0},
                # agno's default (8192) cut off long beat documents and plans mid-reply; at effort
                # "high" haiku's thinking counts here too and used all of 16384 on a narration plan
                max_tokens=32768,
                # Repairs and the parallel scenes resend the same long system prompt: read it
                # from the prompt cache instead of paying full input price each time.
                cache_system_prompt=True,
            )
            effort = reasoning_effort(model_id)
            if effort:
                claude.output_config = {"effort": effort}
            # Native structured output forces additionalProperties=false on every object, so
            # free-form maps (worked_examples[].values) can only come back empty. Use
            # prompt-guided JSON like the other providers. (__post_init__ sets the flag, so
            # it has to be cleared after construction.)
            claude.supports_native_structured_outputs = False
            return claude
        if model_id.startswith(RESPONSES_API_PREFIXES):
            return OpenResponses(
                id=model_id,
                name="OpenCode",
                provider="OpenCode",
                api_key=api_key,
                base_url=base_url,
                default_headers=headers,
                supports_native_structured_outputs=False,
            )
        chat_model = ReasoningOpenAILike if model_id.startswith(RESEND_REASONING_PREFIXES) else OpenAILike
        return chat_model(
            id=model_id,
            name="OpenCode",
            provider="OpenCode",
            api_key=api_key,
            base_url=base_url,
            default_headers=headers,
            # Not every routed model honours response_format=json_schema;
            # fall back to prompt-guided JSON, which validators.py parses.
            supports_native_structured_outputs=False,
            reasoning_effort=reasoning_effort(model_id),
        )
    if provider == "minimax":
        return MiniMax(id=os.getenv("KONVEY_MODEL_ID", DEFAULT_MODEL_ID))
    if provider == "inception":
        api_key = os.getenv("INCEPTION_API_KEY")
        if not api_key:
            raise RuntimeError("KONVEY_PROVIDER=inception needs INCEPTION_API_KEY (get one at https://platform.inceptionlabs.ai)")
        return InceptionChat(
            id=os.getenv("INCEPTION_MODEL_ID", INCEPTION_DEFAULT_MODEL_ID),
            name="Inception",
            provider="Inception",
            api_key=api_key,
            base_url=os.getenv("INCEPTION_BASE_URL", INCEPTION_BASE_URL),
            # Prompt-guided JSON, the same path as the other providers (validators.py parses it).
            supports_native_structured_outputs=False,
            # instant | low | medium | high; mercury-3's server default is low.
            reasoning_effort=os.getenv("KONVEY_EFFORT") or INCEPTION_EFFORT,
            # The cap counts reasoning; at medium the server default (65,536) can all go on
            # reasoning and leave no document. 131,072 is mercury-3's maximum.
            max_completion_tokens=131072,
            # Free tier: 100k output tokens a minute, which three scenes in parallel pass.
            retries=6,
            delay_between_retries=15,
            exponential_backoff=True,
        )
    raise ValueError(f"Unknown KONVEY_PROVIDER {provider!r}; use opencode, opencode-go, minimax or inception")


def create_knowledge_agent(
    model: Optional[ModelLike] = None,
    mode: PromptMode = "few-shot",
    grounded: bool = True,
    compute_log: Optional[ComputeLog] = None,
) -> Agent:
    # calc + run_python, so series and walkthrough states are computed.
    tools = make_tools(compute_log)
    return Agent(
        name="KnowledgeDiscovery",
        model=resolve_model(model),  # type: ignore[arg-type]
        description="3Blue1Brown-style knowledge distillation. Outputs strict JSON, no visuals, no code.",
        instructions=build_agent_instructions(1, mode, grounded),
        output_schema=KnowledgePack,
        tools=tools,
        tool_call_limit=MAX_TOOL_CALLS,
        markdown=False,
    )


def create_planning_agent(
    model: Optional[ModelLike] = None,
    mode: PromptMode = "few-shot",
    grounded: bool = True,
) -> Agent:
    # Stage-only schema and description: agno puts the output schema in the system prompt
    # (see StagePlan).
    return Agent(
        name="StagePlanner",
        model=resolve_model(model),  # type: ignore[arg-type]
        description="Plans 3 scenes S1->S2->S3: narration lines and the objects each beat shows. "
                    "No layout, no animation, no code. Strict JSON.",
        instructions=build_agent_instructions(2, mode, grounded),
        output_schema=StagePlan,
        markdown=False,
    )


def create_coding_agent(
    model: Optional[ModelLike] = None,
    mode: PromptMode = "few-shot",
    grounded: bool = True,
) -> Agent:
    return Agent(
        name="StageDirector",
        model=resolve_model(model),  # type: ignore[arg-type]
        description="Turns one SCENE_SPEC into beat HTML (konvey.stage): layout by CSS, drawn by Manim.",
        instructions=build_agent_instructions(3, mode, grounded),
        markdown=False,
    )
