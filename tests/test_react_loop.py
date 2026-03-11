import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _make_mock_scores(total=85):
    """Helper to create a valid scores dict."""
    return {
        "total_score": total,
        "buzzword_score": 30,
        "length_score": 15,
        "structure_score": 15,
        "authenticity_score": 25,
    }


@patch("brain.react_loop.request_approval")
@patch("brain.react_loop.generate_and_score_post")
@patch("brain.react_loop.get_trending_topics")
@patch("brain.react_loop.generate_image", return_value=None)
@patch("brain.react_loop.Poster")
@patch("brain.react_loop.Memory")
def test_all_decision_routes(
    MockMemory, MockPoster, mock_img, mock_research, mock_gen, mock_approval
):
    """
    Verifies that agent_loop handles all 7 decision strings
    (approve, regenerate, edit, new_topic, skip, timeout, error)
    without crashing, using mocks so no live API calls are needed.
    """
    from brain.react_loop import agent_loop

    # Common setup for every sub-test
    mock_gen.return_value = ("Test post content about AI.", _make_mock_scores(85))

    poster_instance = MagicMock()
    poster_instance.post_text_only.return_value = {"success": True, "post_id": "test123"}
    poster_instance.post_with_image.return_value = {"success": True, "post_id": "test456"}
    MockPoster.return_value = poster_instance

    memory_instance = MagicMock()
    memory_instance.get_last_post_id.return_value = 1
    MockMemory.return_value = memory_instance

    # We also need to mock _safe_notify and _safe_notify_error to prevent real Telegram calls
    with patch("brain.react_loop._safe_notify_error"), \
         patch("brain.react_loop._safe_notify"):

        # ─── Test 1: approve ───
        mock_approval.return_value = "approve"
        agent_loop("test topic")  # should not raise

        # ─── Test 2: skip ───
        mock_approval.return_value = "skip"
        agent_loop("test topic")

        # ─── Test 3: timeout ───
        mock_approval.return_value = "timeout"
        agent_loop("test topic")

        # ─── Test 4: error ───
        mock_approval.return_value = "error"
        agent_loop("test topic")

        # ─── Test 5: regenerate ───
        # Regenerate calls agent_loop recursively, so we mock that recursion
        # by having the second call return "approve" to stop recursion
        call_count = 0
        def regenerate_then_approve(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "regenerate"
            return "approve"

        mock_approval.side_effect = regenerate_then_approve
        agent_loop._retry_count = 0
        agent_loop("test topic")
        mock_approval.side_effect = None  # reset

        # ─── Test 6: new_topic ───
        # new_topic calls agent_loop() with no args (auto-research)
        # We mock research to return a topic, then approval returns "approve"
        mock_research.return_value = {"recommended_topic": "AI agents in 2025"}
        call_count_nt = 0
        def new_topic_then_approve(*args, **kwargs):
            nonlocal call_count_nt
            call_count_nt += 1
            if call_count_nt == 1:
                return "new_topic"
            return "approve"

        mock_approval.side_effect = new_topic_then_approve
        agent_loop._retry_count = 0
        agent_loop("test topic")
        mock_approval.side_effect = None

        # ─── Test 7: edit ───
        mock_approval.return_value = "edit"
        with patch("brain.react_loop.request_text_reply", create=True) as mock_text_reply:
            # Patch at the import location inside the elif block
            with patch("telegram_bot.approval.request_text_reply", return_value="Edited post text here"):
                agent_loop("test topic")

    # If we got here without any exception, all decision routes work
    assert True, "All 7 decision routes handled without errors"
