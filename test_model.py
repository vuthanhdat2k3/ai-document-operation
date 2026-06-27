"""Test each agent's model configuration by calling the LLM directly.

Usage:
    docker compose exec api python /app/test_model.py
    # or copy to container:
    docker cp test_model.py docops-api:/app/ && docker compose exec api python /app/test_model.py
"""

import asyncio
import sys
import time

from app.config import get_settings
from app.llm.factory import get_llm_provider
from app.llm.base import Message


async def test_agent_model(name: str, system_prompt: str, user_query: str) -> dict:
    """Test an agent's model by making a direct LLM call with its system prompt."""
    settings = get_settings()
    provider = get_llm_provider(settings)

    messages = [Message(role="user", content=user_query)]

    print(f"\n{'='*60}")
    print(f"  Agent: {name}")
    print(f"  Model: {settings.LLM_MODEL}")
    print(f"  Base:  {settings.OPENAI_API_BASE}")
    print(f"{'='*60}")

    start = time.time()
    try:
        response = await provider.chat(
            messages=messages,
            model=settings.LLM_MODEL,
            system=system_prompt,
            max_tokens=256,
            temperature=0.1,
        )
        elapsed = time.time() - start
        print(f"  ✅ OK ({elapsed:.1f}s)")
        print(f"  Input tokens:  {response.input_tokens}")
        print(f"  Output tokens: {response.output_tokens}")
        print(f"  Finish reason: {response.finish_reason}")
        print(f"  Response ({len(response.content)} chars):")
        print(f"  ──")
        # Truncate long responses
        content = response.content
        if len(content) > 500:
            content = content[:500] + "..."
        for line in content.split("\n"):
            print(f"  {line}")
        return {"status": "ok", "elapsed": elapsed, "tokens": response.output_tokens}
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ FAILED ({elapsed:.1f}s): {e}")
        return {"status": "error", "elapsed": elapsed, "error": str(e)}


async def test_provider_direct() -> dict:
    """Test the raw provider with the simplest possible call."""
    settings = get_settings()
    provider = get_llm_provider(settings)

    messages = [Message(role="user", content="Say exactly: OK")]

    print(f"\n{'='*60}")
    print(f"  DIRECT PROVIDER TEST")
    print(f"  Provider: {provider.provider_name}")
    print(f"  Model:    {settings.LLM_MODEL}")
    print(f"  Base:     {settings.OPENAI_API_BASE}")
    print(f"{'='*60}")

    start = time.time()
    try:
        response = await provider.chat(
            messages=messages,
            model=settings.LLM_MODEL,
            max_tokens=16,
            temperature=0.0,
        )
        elapsed = time.time() - start
        print(f"  ✅ OK ({elapsed:.1f}s)")
        content = response.content.strip()
        print(f"  Response: \"{content}\"")
        return {"status": "ok", "elapsed": elapsed, "content": content}
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ FAILED ({elapsed:.1f}s): {e}")
        return {"status": "error", "elapsed": elapsed, "error": str(e)}


async def main():
    print("=" * 60)
    print("  LLM MODEL TEST")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = []

    # 1. Direct provider test first
    r = await test_provider_direct()
    results.append(("direct", r))
    if r["status"] == "error":
        print("\n  ❌ Direct provider test FAILED — stopping further tests.")
        print("  Check: API key, base URL, and model name.")
        sys.exit(1)

    # 2. Test with each agent's system prompt
    agents = [
        (
            "doc-qa",
            "You are a document operations agent. Answer the user's question about documents.",
            "What documents do you have access to?",
        ),
        (
            "chat",
            "You are a helpful AI assistant. Answer the user's questions concisely.",
            "Hello! What can you help me with?",
        ),
        (
            "summarise",
            "You are a document summarisation agent. Generate concise summaries.",
            "Summarise this: The board approved the Q3 budget of $2M.",
        ),
        (
            "router",
            "You are an intelligent request router. Route queries to specialist agents.",
            "I need to find a contract that expires next month.",
        ),
    ]

    for name, system_prompt, query in agents:
        r = await test_agent_model(name, system_prompt, query)
        results.append((name, r))

    # Summary
    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for _, r in results if r["status"] == "ok")
    failed = sum(1 for _, r in results if r["status"] == "error")
    for name, r in results:
        status = "✅" if r["status"] == "ok" else "❌"
        print(f"  {status} {name:10s}  {r.get('elapsed', 0):5.1f}s  {r.get('error', '')}")
    print(f"\n  Passed: {passed}/{len(results)}")
    if failed:
        print(f"  Failed: {failed}/{len(results)}")
        sys.exit(1)
    print("  All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
