import re
from modules.writer import generate_post, get_banned_phrases

def score_buzzwords(post_text: str) -> int:
    banned = get_banned_phrases()
    if not banned:
        return 30
    
    score = 30
    text_lower = post_text.lower()
    for phrase in banned:
        if phrase.lower() in text_lower:
            score -= 10
    
    return max(0, score)

def score_length(post_text: str) -> int:
    words = len(post_text.split())
    if 150 <= words <= 250:
        return 15
    elif 100 <= words < 150 or 250 < words <= 300:
        return 10
    else:
        return 5

def score_structure(post_text: str) -> int:
    score = 0
    lines = [line.strip() for line in post_text.split("\n") if line.strip()]
    if lines and len(lines[0].split()) <= 15:
        score += 5
    
    if re.search(r'#[a-zA-Z0-9_]+', post_text):
        score += 5
        
    if len(lines) >= 3:
        score += 5
        
    return score

def score_authenticity(post_text: str) -> int:
    score = 20
    text_lower = post_text.lower()
    if " i " in text_lower or text_lower.startswith("i "):
        score += 10
    
    sentences = re.split(r'[.!?]+', post_text)
    words_in_sentences = [len(s.split()) for s in sentences if s.strip()]
    if words_in_sentences:
        avg_len = sum(words_in_sentences) / len(words_in_sentences)
        if 8 <= avg_len <= 18:
            score += 10
    
    return min(40, score)

def score_post(post_text: str) -> dict:
    buzzword_score = score_buzzwords(post_text)
    length_score = score_length(post_text)
    structure_score = score_structure(post_text)
    authenticity_score = score_authenticity(post_text)
    
    total_score = buzzword_score + length_score + structure_score + authenticity_score
    
    return {
        "total_score": total_score,
        "buzzword_score": buzzword_score,
        "length_score": length_score,
        "structure_score": structure_score,
        "authenticity_score": authenticity_score
    }

def contains_banned_phrase(post_text: str) -> str | None:
    """
    Hard code-level check — returns the first banned phrase found
    in the post, or None if clean. This enforces the ban in Python,
    not just via LLM prompt (which the model can ignore).
    """
    banned = get_banned_phrases()
    text_lower = post_text.lower()
    for phrase in banned:
        if phrase.lower() in text_lower:
            return phrase
    return None


def generate_and_score_post(topic: str, angle: str, hook: str, max_retries: int = 3) -> tuple[str, dict]:
    """Generates a post and rewrites if score is below 70, keeping track of the best one."""
    from rich.console import Console
    console = Console()
    
    best_post = None
    best_scores = {"total_score": 0}
    
    for attempt in range(max_retries):
        console.print(f"[dim]Generating post (Attempt {attempt + 1})...[/dim]")
        post = generate_post(topic, angle, hook)
        
        if post and not post.startswith("Error"):
            # Hard enforcement — if LLM used a banned phrase, force retry
            # but still track it as a last-resort fallback so best_post is never None
            violation = contains_banned_phrase(post)
            if violation:
                console.print(f"[yellow]Banned phrase detected: '{violation}'. Forcing retry...[/yellow]")
                # Track as fallback only — score it so we have something if all retries fail
                fallback_scores = score_post(post)
                if best_post is None or fallback_scores["total_score"] > best_scores["total_score"]:
                    best_post = post
                    best_scores = fallback_scores
                continue

            scores = score_post(post)
            # Log the voice score
            try:
                from modules.memory import Memory
                m = Memory()
                m.save_voice_score(scores['authenticity_score'], scores['buzzword_score'], scores['total_score'])
            except Exception as e:
                console.print(f"[dim yellow]Warning logging voice score: {e}[/dim yellow]")
                
            # Track the highest scorer across retries
            if scores["total_score"] > best_scores["total_score"]:
                best_scores = scores
                best_post = post
                
            if scores["total_score"] >= 70:
                console.print(f"[green]Post generated successfully with score {scores['total_score']}/100[/green]")
                return post, scores
            else:
                console.print(f"[yellow]Score {scores['total_score']} below 70, retrying...[/yellow]")
        else:
            console.print(f"[red]Generation failed: {post}[/red]")
            # Return immediately if API completely crashed
            if best_post is None:
                return post, {"total_score": 0}
            
    console.print(f"[bold yellow]Warning: Max retries reached. Keeping best available post (Score: {best_scores['total_score']}).[/bold yellow]")
    return best_post, best_scores
