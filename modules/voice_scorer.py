import re
from modules.writer import generate_post, get_banned_phrases

# Compile once at module load — reused across all scoring calls
_HASHTAG_RE = re.compile(r'#[a-zA-Z0-9_]+')
_SENTENCE_SPLIT_RE = re.compile(r'[.!?]+')

# Built once on first call, reused for lifetime of process
_BANNED_SET: frozenset[str] = frozenset()

def _get_banned_set() -> frozenset[str]:
    global _BANNED_SET
    if not _BANNED_SET:
        _BANNED_SET = frozenset(p.lower() for p in get_banned_phrases())
    return _BANNED_SET


def score_buzzwords(post_text: str) -> int:
    banned = _get_banned_set()
    if not banned:
        return 30
    text_lower = post_text.lower()
    hits = sum(1 for p in banned if p in text_lower)
    return max(0, 30 - hits * 10)


def score_length(post_text: str) -> int:
    words = len(post_text.split())
    if 150 <= words <= 250:    return 15
    if 100 <= words <= 300:    return 10
    return 5


def score_structure(post_text: str) -> int:
    lines = [l.strip() for l in post_text.split("\n") if l.strip()]
    score = 0
    if lines and len(lines[0].split()) <= 15:    score += 5
    if _HASHTAG_RE.search(post_text):            score += 5
    if len(lines) >= 3:                          score += 5
    return score


def score_authenticity(post_text: str) -> int:
    text_lower = post_text.lower()
    score = 20
    if " i " in text_lower or text_lower.startswith("i "):
        score += 10
    parts = [s.split() for s in _SENTENCE_SPLIT_RE.split(post_text) if s.strip()]
    if parts:
        avg = sum(len(p) for p in parts) / len(parts)
        if 8 <= avg <= 18:
            score += 10
    return min(40, score)


def score_post(post_text: str) -> dict:
    bz = score_buzzwords(post_text)
    ln = score_length(post_text)
    st = score_structure(post_text)
    au = score_authenticity(post_text)
    return {
        "total_score": bz + ln + st + au,
        "buzzword_score": bz,
        "length_score": ln,
        "structure_score": st,
        "authenticity_score": au,
    }


def contains_banned_phrase(post_text: str) -> str | None:
    """O(1) set lookup per phrase vs O(n) per call previously."""
    text_lower = post_text.lower()
    for phrase in _get_banned_set():
        if phrase in text_lower:
            return phrase
    return None


def generate_and_score_post(topic: str, angle: str, hook: str,
                             max_retries: int = 3) -> tuple[str, dict]:
    from rich.console import Console
    from modules.memory import Memory
    console = Console()

    best_post = None
    best_scores = {"total_score": 0}
    mem = Memory()   # single instance for all retries

    for attempt in range(max_retries):
        console.print(f"[dim]Generating post (Attempt {attempt + 1})...[/dim]")
        post = generate_post(topic, angle, hook)

        if not post or post.startswith("Error"):
            console.print(f"[red]Generation failed: {post}[/red]")
            if best_post is None:
                return post, {"total_score": 0}
            continue

        violation = contains_banned_phrase(post)
        if violation:
            console.print(f"[yellow]Banned phrase detected: '{violation}'. Forcing retry...[/yellow]")
            fb = score_post(post)
            if best_post is None or fb["total_score"] > best_scores["total_score"]:
                best_post, best_scores = post, fb
            continue

        scores = score_post(post)
        try:
            mem.save_voice_score(scores["authenticity_score"],
                                 scores["buzzword_score"],
                                 scores["total_score"])
        except Exception as e:
            console.print(f"[dim yellow]Warning logging voice score: {e}[/dim yellow]")

        if scores["total_score"] > best_scores["total_score"]:
            best_post, best_scores = post, scores

        if scores["total_score"] >= 70:
            console.print(f"[green]Post generated with score {scores['total_score']}/100[/green]")
            return post, scores
        console.print(f"[yellow]Score {scores['total_score']} below 70, retrying...[/yellow]")

    console.print(f"[bold yellow]Max retries. Best score: {best_scores['total_score']}[/bold yellow]")
    return best_post, best_scores
