#!/usr/bin/env python3
"""Example script demonstrating the research agent usage."""

import asyncio

from research_agent import get_settings
from research_agent.logging_config import get_logger, setup_logging


def main() -> None:
    """Main example function."""
    settings = get_settings()
    setup_logging(settings.logging)

    logger = get_logger(__name__)

    logger.info(
        "Research Agent Example",
        environment=settings.environment,
        llm_provider=settings.llm.provider.value,
        storage_backend=settings.storage.backend.value,
    )

    print("\n" + "=" * 70)
    print("Research Agent - Example Script")
    print("=" * 70)
    print(f"\nEnvironment: {settings.environment}")
    print(f"LLM Provider: {settings.llm.provider.value}")
    print(f"Storage Backend: {settings.storage.backend.value}")
    print(f"Recursion Limit: {settings.agent.recursion_limit}")
    print(f"Cost Cap: ${settings.agent.cost_cap_usd}")
    print("\n" + "=" * 70)
    print("\nThe agent execution logic will be implemented in future iterations.")
    print("For now, you can use:")
    print("  - CLI: research-agent run <thread_id> <query>")
    print("  - API: research-agent serve")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
