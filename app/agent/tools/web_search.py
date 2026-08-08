
import asyncio
import time
from langchain_core.tools import tool
from ddgs import DDGS
from app.core.logging import get_logger

log = get_logger(__name__)


def _ddg_search(query: str) -> list[dict]:
    """Synchronous DDG search with retry — called from run_in_executor."""
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query[:200], max_results=5))
                if results:
                    return results
        except Exception as e:
            log.warning("ddg_retry: attempt=%s error=%s", attempt + 1, str(e))
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s then 2s
            else:
                raise
    return []


@tool
async def web_search(query: str) -> str:
    """
    Search the web and return relevant results.
    Use this tool for any current information, recent events,
    or facts you cannot answer with confidence.
    Arguments:
        query: The search request in natural language.
    """
    try:
        results = await asyncio.get_running_loop().run_in_executor(
            None, _ddg_search, query
        )

        if not results:
            return f"No results found for: {query}"

        formatted = [
            f"**{r.get('title', 'No title')}**\n"
            f"{r.get('body', '')}\n"
            f"Source: {r.get('href', '')}"
            for r in results[:3]
        ]

        log.info("web_search_done: query=%s results=%s", query[:50], len(results))
        return "\n\n---\n\n".join(formatted)  

    except Exception as e:
        log.error("web_search_error: error=%s query=%s", str(e), query[:100])
        return f"Error during search: {str(e)}"