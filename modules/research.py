import os
import random

import feedparser
from googlesearch import search
from rich.console import Console

console = Console()

# Defined feeds from blueprint
RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://hnrss.org/frontpage",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://blog.google/technology/ai/rss/"
]

NICHE_KEYWORDS = [
    "Python", "Flask", "Backend Development",
    "AI", "Machine Learning", "LLMs",
    "Cloud", "PostgreSQL", "REST APIs",
    "AI agents", "open source", "developer",
    "API", "GitHub", "automation", "startup"
]

def get_used_topics(days: int = 7) -> list[str]:
    """Fetch topics used in the last N days from memory.db to avoid repetition."""
    try:
        from modules.memory import Memory
        m = Memory()
        return m.get_recent_topics(days)
    except Exception as e:
        console.print(f"[dim yellow]Warning reading memory.db: {e}[/dim yellow]")
        return []

def get_rss_trends() -> list[dict]:
    """Fetch recent articles from relevant RSS feeds."""
    trends = []
    
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            # Take top 3 entries from each feed
            for entry in feed.entries[:3]:
                # Keyword filter applies to all feeds
                title_lower = entry.title.lower()
                is_relevant = any(kw.lower() in title_lower for kw in NICHE_KEYWORDS)
                
                if is_relevant:
                    trends.append({
                        "title": entry.title,
                        "link": entry.link,
                        "source": feed.feed.title if hasattr(feed.feed, 'title') else feed_url
                    })
        except Exception as e:
            console.print(f"[yellow]Failed to parse feed {feed_url}: {e}[/yellow]")
            continue
            
    return trends

def get_google_search_trends() -> list[str]:
    """Search Google for recent LinkedIn posts in Ansh's niche."""
    query = 'site:linkedin.com ("Python" OR "AI" OR "Backend") "reactions" "comments"'
    results = []
    
    try:
        search_results = search(query, num_results=5, lang="en")
        for url in search_results:
            results.append(url)
    except Exception as e:
        console.print(f"[dim yellow]Warning during Google Search: {e}[/dim yellow]")
        
    return results

def score_and_select_topic(rss_trends: list[dict], search_trends: list[str], used_topics: list[str]) -> dict:
    """Consolidate research and select the best topic."""
    
    trending_topics = []
    top_posts_summary = []
    
    # Process RSS trends into topic strings
    for item in rss_trends:
        topic = item["title"]
        if topic not in used_topics:
            trending_topics.append(topic)
            top_posts_summary.append(f"[{item['source']}] {topic}")
            
    # If no RSS trends match, use some defaults based on keywords
    if not trending_topics:
        trending_topics = [
            "Building AI agents for backend workflows",
            "Python 3.13 features for backend devs",
            "Optimizing PostgreSQL queries in heavy APIs"
        ]
        
    # Filter out anything used recently
    available_topics = [t for t in trending_topics if t not in used_topics]
    
    if not available_topics:
        # Fallback if somehow everything is used
        available_topics = ["Reflections on backend architecture scaling"]
        
    # Randomly pick from top 3 to avoid same topic repeating every run
    best_topic = random.choice(available_topics[:3])
    
    # Add Google search context if available
    for link in search_trends[:3]:
        top_posts_summary.append(f"[LinkedIn Search] Relevant discussion found at: {link}")
        
    return {
        "trending_topics": available_topics[:5],
        "top_posts_summary": top_posts_summary[:5],
        "recommended_topic": best_topic,
        "reasoning": f"Relevant to niche keywords. Has not been posted about in the last 7 days."
    }

def get_trending_topics() -> dict:
    """Main entry point for the research module."""
    console.print("[dim]Starting research module...[/dim]")
    
    cooldown = int(os.environ.get("TOPIC_COOLDOWN_DAYS", 7))
    used_topics = get_used_topics(days=cooldown)
    console.print(f"[dim]Found {len(used_topics)} topics recently used.[/dim]")
    
    rss_trends = get_rss_trends()
    console.print(f"[dim]Analyzed {len(rss_trends)} relevant RSS articles.[/dim]")
    
    search_trends = get_google_search_trends()
    console.print(f"[dim]Found {len(search_trends)} relevant LinkedIn discussions via Search.[/dim]")
    
    result = score_and_select_topic(rss_trends, search_trends, used_topics)
    return result
