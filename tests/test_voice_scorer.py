import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.voice_scorer import score_buzzwords, score_length, score_structure, score_authenticity, score_post

def test_score_buzzwords():
    # A post with no buzzwords
    good_post = "I built a cool tool today using Python."
    score = score_buzzwords(good_post)
    assert score == 30

    # A post with buzzwords (e.g. leverage, synergy)
    bad_post = "I am thrilled to announce that we will leverage synergy for a paradigm shift."
    bad_score = score_buzzwords(bad_post)
    assert bad_score < 30

def test_score_length():
    post_short = "Too short."
    assert score_length(post_short) == 5
    
    post_perfect = " ".join(["word"] * 200)
    assert score_length(post_perfect) == 15

def test_score_structure():
    post = "First line is short.\n\nThen a block.\n\n#hashtags"
    assert score_structure(post) > 0

def test_score_authenticity():
    post = "I really struggled to learn this. But eventually I got it. It was hard."
    assert score_authenticity(post) > 20

def test_score_post():
    post = "I learned a lot today building my AI agent. It was a solid learning experience. #python"
    scores = score_post(post)
    assert "total_score" in scores
    assert scores["total_score"] > 0
