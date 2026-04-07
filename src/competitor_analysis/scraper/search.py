from __future__ import annotations

import json
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from rich.console import Console

from competitor_analysis import config
from competitor_analysis.models import SearchResult

_CACHE_DIR = Path(__file__).parent.parent.parent.parent / ".cache" / "search"
_CACHE_TTL = timedelta(hours=24)
_SERPAPI_BASE = "https://serpapi.com/search"


def _cache_path(query: str) -> Path:
    key = hashlib.md5(query.encode()).hexdigest()
    return _CACHE_DIR / f"{key}.json"


def _load_cache(query: str) -> list[SearchResult] | None:
    path = _cache_path(query)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    cached_at = datetime.fromisoformat(data["cached_at"])
    if datetime.now() - cached_at > _CACHE_TTL:
        return None
    return [SearchResult(**r) for r in data["results"]]


def _save_cache(query: str, results: list[SearchResult]) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(query)
    path.write_text(
        json.dumps(
            {
                "cached_at": datetime.now().isoformat(),
                "query": query,
                "results": [r.model_dump() for r in results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def search(query: str, use_cache: bool = True, verbose: bool = False) -> list[SearchResult]:
    """Search the web using SerpAPI. Returns up to 10 organic results."""
    console = Console()

    if use_cache:
        cached = _load_cache(query)
        if cached is not None:
            if verbose:
                console.print(f"  [dim]Cache hit for: {query}[/dim]")
            return cached

    api_key = config.require("SERPAPI_KEY")

    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": 10,
        "hl": "it",
        "gl": "it",
    }

    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(_SERPAPI_BASE, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        if verbose:
            console.print(f"[yellow]Search API error for '{query}': {exc}[/yellow]")
        return []

    organic = data.get("organic_results", [])
    results = [
        SearchResult(
            title=item.get("title", ""),
            url=item.get("link", ""),
            snippet=item.get("snippet", ""),
        )
        for item in organic
        if item.get("link")
    ]

    if verbose:
        console.print(f"  [dim]SerpAPI: {len(results)} results for: {query}[/dim]")

    if use_cache:
        _save_cache(query, results)

    # Be polite to the API
    time.sleep(0.5)

    return results
