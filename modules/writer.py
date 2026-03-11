import os
from groq import Groq
from dotenv import load_dotenv
from brain.prompts import SYSTEM_PROMPT

# Load environment variables
load_dotenv()

def get_banned_phrases():
    try:
        # Construct path relative to main execution directory
        filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voice_profile", "banned_phrases.txt")
        with open(filepath, "r") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except Exception:
        return []

def get_style_guide():
    try:
        filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voice_profile", "style_guide.txt")
        with open(filepath, "r") as f:
            return f.read()
    except Exception:
        return ""

def get_sample_posts():
    try:
        filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voice_profile", "sample_posts.txt")
        with open(filepath, "r") as f:
            return f.read()
    except Exception:
        return "No sample posts provided."

def generate_post(topic: str, angle: str, hook: str) -> str:
    """
    Generate a LinkedIn post using Groq API and Ansh's voice profile.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "Error: GROQ_API_KEY not found in environment."

    client = Groq(api_key=api_key)
    
    banned_phrases = ", ".join(get_banned_phrases())
    style_guide = get_style_guide()
    sample_posts = get_sample_posts()
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"BANNED PHRASES TO AVOID:\n{banned_phrases}\n\nSTYLE GUIDE:\n{style_guide}"
                },
                {
                    "role": "user",
                    "content": SYSTEM_PROMPT.format(sample_posts=sample_posts, topic=topic, angle=angle, hook=hook),
                }
            ],
            # Using latest Llama 3 model on Groq for fastest and highest quality responses.
            # Replace with "llama-4" string whenever it becomes available as per blueprint.
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=1024,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Error generating post: {str(e)}"
