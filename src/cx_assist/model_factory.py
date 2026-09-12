from __future__ import annotations

import os

from langchain_core.language_models.chat_models import BaseChatModel

from .config import settings


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is missing")
    return value


def build_chat_model() -> tuple[BaseChatModel, str]:
    provider = settings.model_provider
    if provider == "groq":
        from langchain_groq import ChatGroq

        model_name = required("GROQ_MODEL")
        return ChatGroq(
            model=model_name,
            api_key=required("GROQ_API_KEY"),
            temperature=settings.model_temperature,
            max_retries=3,
            timeout=90,
        ), model_name
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        model_name = required("GOOGLE_MODEL")
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=required("GOOGLE_API_KEY"),
            temperature=settings.model_temperature,
            max_retries=3,
            timeout=90,
        ), model_name
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        model_name = required("OPENAI_MODEL")
        return ChatOpenAI(
            model=model_name,
            api_key=required("OPENAI_API_KEY"),
            temperature=settings.model_temperature,
            max_retries=3,
            timeout=90,
        ), model_name
    raise RuntimeError(f"Unsupported MODEL_PROVIDER: {provider}")

