"""
HOA Audit Swarm — Environment Configuration

Shared setup for all modules:
- Loads .env
- Suppresses the Pydantic V1 deprecation warning from langchain-core
- Auto-detects LLM provider: Claude → Gemini → OpenAI
"""

import warnings
import os
from dotenv import load_dotenv

# Suppress the langchain-core Pydantic V1 warning on Python 3.14+
warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14",
    category=UserWarning,
)

load_dotenv()


def get_llm(model: str | None = None, temperature: float = 0):
    """
    Get the configured LLM. Auto-detects provider based on available API keys.
    Priority: Claude → Gemini → OpenAI

    Args:
        model: Override model name. If None, uses best available.
        temperature: LLM temperature (0 = deterministic).
    """
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model or "claude-sonnet-4-20250514",
            temperature=temperature,
        )
    elif os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.5-pro",
            temperature=temperature,
        )
    elif os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            temperature=temperature,
        )
    else:
        raise ValueError(
            "No API key found. Set one of: ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY in .env"
        )
