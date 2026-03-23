import os
from functools import lru_cache
from groq import Groq
from dotenv import load_dotenv
from brain.prompts import SYSTEM_PROMPT

load_dotenv()

# --- Module-level cache: files read ONCE per process, not per call ---

@lru_cache(maxsize=1)
def get_banned_phrases() -> tuple[str, ...]:
    """Returns a tuple (hashable/cacheable). Read from disk exactly once."""
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "voice_profile", "banned_phrases.txt")
        with open(path) as f:
            return tuple(line.strip() for line in f if line.strip())
    except Exception:
        return ()

@lru_cache(maxsize=1)
def _get_style_guide() -> str:
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "voice_profile", "style_guide.txt")
        with open(path) as f:
            return f.read()
    except Exception:
        return ""

@lru_cache(maxsize=1)
def _get_sample_posts() -> str:
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "voice_profile", "sample_posts.txt")
        with open(path) as f:
            return f.read()
    except Exception:
        return "No sample posts provided."

@lru_cache(maxsize=1)
def _get_groq_client() -> Groq:
    """Single Groq client reused across all calls."""
    return Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

@lru_cache(maxsize=1)
def _get_system_message() -> str:
    """Build system message once — banned phrases + style guide never change mid-run."""
    return (f"BANNED PHRASES TO AVOID:\n{', '.join(get_banned_phrases())}"
            f"\n\nSTYLE GUIDE:\n{_get_style_guide()}")


def generate_post(topic: str, angle: str, hook: str) -> str:
    if not os.environ.get("GROQ_API_KEY"):
        return "Error: GROQ_API_KEY not found in environment."
    try:
        completion = _get_groq_client().chat.completions.create(
            messages=[
                {"role": "system", "content": _get_system_message()},
                {"role": "user", "content": SYSTEM_PROMPT.format(
                    sample_posts=_get_sample_posts(),
                    topic=topic, angle=angle, hook=hook
                )},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=1024,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error generating post: {e}"
