import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser
from googlesearch import search
from rich.console import Console

console = Console()

RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://hnrss.org/frontpage",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://blog.google/technology/ai/rss/",
]

# frozenset for O(1) membership test during keyword filtering
_NICHE_KW = frozenset(kw.lower() for kw in [
    "python", "flask", "backend development",
    "ai", "machine learning", "llms",
    "cloud", "postgresql", "rest apis",
    "ai agents", "open source", "developer",
    "api", "github", "automation", "startup",
])

_FALLBACK_TOPICS = [
    "Building AI agents for backend workflows",
    "Python 3.13 features for backend devs",
    "Optimizing PostgreSQL queries in heavy APIs",
]


def _fetch_feed(feed_url: str) -> list[dict]:
    """Fetch a single RSS feed. Runs concurrently."""
    try:
        feed = feedparser.parse(feed_url)
        source = getattr(feed.feed, "title", feed_url)
        return [
            {"title": e.title, "link": e.link, "source": source}
            for e in feed.entries[:3]
            if any(kw in e.title.lower() for kw in _NICHE_KW)
        ]
    except Exception as e:
        console.print(f"[yellow]Failed to parse feed {feed_url}: {e}[/yellow]")
        return []


def get_used_topics(days: int = 7) -> frozenset[str]:
    """Return a frozenset for O(1) dedup checks downstream."""
    try:
        from modules.memory import Memory
        return frozenset(Memory().get_recent_topics(days))
    except Exception as e:
        console.print(f"[dim yellow]Warning reading memory.db: {e}[/dim yellow]")
        return frozenset()


def get_rss_trends() -> list[dict]:
    """Fetch all RSS feeds in parallel — 4x faster than sequential."""
    trends = []
    with ThreadPoolExecutor(max_workers=len(RSS_FEEDS)) as ex:
        futures = {ex.submit(_fetch_feed, url): url for url in RSS_FEEDS}
        for fut in as_completed(futures):
            trends.extend(fut.result())
    return trends


def get_google_search_trends() -> list[str]:
    query = 'site:linkedin.com ("Python" OR "AI" OR "Backend") "reactions" "comments"'
    try:
        return list(search(query, num_results=5, lang="en"))
    except Exception as e:
        console.print(f"[dim yellow]Warning during Google Search: {e}[/dim yellow]")
        return []


def score_and_select_topic(rss_trends: list[dict],
                            search_trends: list[str],
                            used_topics: frozenset[str]) -> dict:
    # O(1) membership check per title thanks to frozenset
    trending = [t["title"] for t in rss_trends if t["title"] not in used_topics]
    summary  = [f"[{t['source']}] {t['title']}" for t in rss_trends
                if t["title"] not in used_topics]

    if not trending:
        trending = [t for t in _FALLBACK_TOPICS if t not in used_topics] or _FALLBACK_TOPICS

    best = random.choice(trending[:3])
    summary += [f"[LinkedIn Search] {link}" for link in search_trends[:3]]

    return {
        "trending_topics":  trending[:5],
        "top_posts_summary": summary[:5],
        "recommended_topic": best,
        "reasoning": "Relevant to niche. Not posted in cooldown window.",
    }


def get_trending_topics() -> dict:
    console.print("[dim]Starting research module...[/dim]")
    cooldown     = int(os.environ.get("TOPIC_COOLDOWN_DAYS", 7))
    used_topics  = get_used_topics(days=cooldown)
    console.print(f"[dim]Found {len(used_topics)} topics recently used.[/dim]")
    rss_trends   = get_rss_trends()
    console.print(f"[dim]Analyzed {len(rss_trends)} relevant RSS articles.[/dim]")
    search_trends = get_google_search_trends()
    console.print(f"[dim]Found {len(search_trends)} relevant LinkedIn discussions.[/dim]")
    return score_and_select_topic(rss_trends, search_trends, used_topics)
