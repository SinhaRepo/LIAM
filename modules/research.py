import os
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser
from bs4 import BeautifulSoup
from googlesearch import search
from rich.console import Console

console = Console()

RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://hnrss.org/frontpage",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://blog.google/technology/ai/rss/",
]

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


def _fetch_article_text(url: str, max_chars: int = 1200) -> str:
    """
    Fetch the actual article content from a URL.
    Returns cleaned text limited to max_chars. Falls back to empty string on failure.
    """
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise: scripts, styles, nav, footer, ads
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "noscript", "figure"]):
            tag.decompose()

        # Extract paragraphs — main article content
        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            if len(text) > 40:   # skip tiny fragments
                paragraphs.append(text)

        content = " ".join(paragraphs)
        return content[:max_chars].strip()
    except Exception:
        return ""


def _fetch_feed(feed_url: str) -> list[dict]:
    """Fetch a single RSS feed. Runs concurrently."""
    try:
        feed = feedparser.parse(feed_url)
        source = getattr(feed.feed, "title", feed_url)
        results = []
        for e in feed.entries[:3]:
            if not any(kw in e.title.lower() for kw in _NICHE_KW):
                continue
            # Get RSS summary if available — free context without an HTTP request
            summary = ""
            if hasattr(e, "summary"):
                soup = BeautifulSoup(e.summary, "html.parser")
                summary = soup.get_text(separator=" ", strip=True)[:600]

            results.append({
                "title": e.title,
                "link": e.link,
                "source": source,
                "summary": summary,
            })
        return results
    except Exception as e:
        console.print(f"[yellow]Failed to parse feed {feed_url}: {e}[/yellow]")
        return []


def get_used_topics(days: int = 7) -> frozenset[str]:
    try:
        from modules.memory import Memory
        return frozenset(Memory().get_recent_topics(days))
    except Exception as e:
        console.print(f"[dim yellow]Warning reading memory.db: {e}[/dim yellow]")
        return frozenset()


def get_rss_trends() -> list[dict]:
    """Fetch all RSS feeds in parallel."""
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


def _build_article_context(item: dict) -> str:
    """
    Build a grounded context string for the LLM.
    First tries the full article, falls back to RSS summary.
    """
    console.print(f"[dim]Fetching article content for: {item['title'][:60]}...[/dim]")

    # Try full article first
    full_text = _fetch_article_text(item["link"])

    if full_text and len(full_text) > 200:
        context = full_text
    elif item.get("summary"):
        context = item["summary"]
    else:
        context = ""

    if not context:
        return ""

    return (
        f"SOURCE: {item['source']}\n"
        f"HEADLINE: {item['title']}\n"
        f"ARTICLE CONTENT:\n{context}"
    )


def score_and_select_topic(rss_trends: list[dict],
                            search_trends: list[str],
                            used_topics: frozenset[str]) -> dict:
    available = [t for t in rss_trends if t["title"] not in used_topics]

    if not available:
        # Fallback topics have no article context
        fallback = [t for t in _FALLBACK_TOPICS if t not in used_topics] or _FALLBACK_TOPICS
        return {
            "trending_topics": fallback[:5],
            "top_posts_summary": [],
            "recommended_topic": random.choice(fallback[:3]),
            "article_context": "",
            "reasoning": "No new RSS articles. Using fallback topic.",
        }

    # Pick from top 3 available
    chosen = random.choice(available[:3])

    # Fetch full article content for the chosen topic
    article_context = _build_article_context(chosen)

    summary = [f"[{t['source']}] {t['title']}" for t in available]
    summary += [f"[LinkedIn Search] {link}" for link in search_trends[:3]]

    return {
        "trending_topics": [t["title"] for t in available[:5]],
        "top_posts_summary": summary[:5],
        "recommended_topic": chosen["title"],
        "article_context": article_context,
        "reasoning": "Relevant to niche. Not posted in cooldown window.",
    }


def get_trending_topics() -> dict:
    console.print("[dim]Starting research module...[/dim]")
    cooldown    = int(os.environ.get("TOPIC_COOLDOWN_DAYS", 7))
    used_topics = get_used_topics(days=cooldown)
    console.print(f"[dim]Found {len(used_topics)} topics recently used.[/dim]")
    rss_trends  = get_rss_trends()
    console.print(f"[dim]Analyzed {len(rss_trends)} relevant RSS articles.[/dim]")
    search_trends = get_google_search_trends()
    console.print(f"[dim]Found {len(search_trends)} relevant LinkedIn discussions.[/dim]")
    return score_and_select_topic(rss_trends, search_trends, used_topics)
