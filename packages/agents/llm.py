import logging

from apps.api.config import settings

logger = logging.getLogger("cortexbi.llm")


def get_llm(temperature: float = 0.1):
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=temperature,
        max_retries=2,
        timeout=120,
    )
    logger.info("LLM initialized: %s @ %s", settings.LLM_MODEL, settings.LLM_BASE_URL)
    return llm


def is_llm_available() -> bool:
    return bool(settings.LLM_API_KEY and settings.LLM_BASE_URL and settings.LLM_MODEL)
