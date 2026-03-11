import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.writer import generate_post, get_banned_phrases

def test_get_banned_phrases():
    phrases = get_banned_phrases()
    assert isinstance(phrases, list)
    if phrases:
        assert isinstance(phrases[0], str)

def test_generate_post():
    # Test generation with a simple prompt
    topic = "The importance of testing in Python"
    angle = "Educational"
    hook = "Why I always write tests first."
    
    post = generate_post(topic, angle, hook)
    
    assert post is not None
    assert isinstance(post, str)
    assert not post.startswith("Error")
    assert len(post) > 50  # Ensure it actually generated content
