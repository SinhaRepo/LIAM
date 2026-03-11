import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.poster import Poster, SafetyError

def test_poster_initialization():
    p = Poster()
    assert p.access_token is not None, "LinkedIn access token must be set in .env"
    assert p.headers["Authorization"].startswith("Bearer")

def test_poster_guardrails():
    # Test that we can't post without approval
    p = Poster()
    try:
        p.perform_safety_checks(human_approved=False)
        assert False, "Safety checks should have failed due to human_approved=False"
    except SafetyError as e:
        assert "not approved" in str(e).lower()
