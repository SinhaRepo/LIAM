import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.memory import Memory

def test_memory():
    print("Testing Memory Module...")
    
    # Initialize Memory
    m = Memory("test_memory.db")
    
    # Save a test post (this also logs the topic)
    print("Saving test post...")
    m.save_post(
        topic="AI agents",
        content="Test post content",
        image_path=None,
        score=95
    )
    
    # Check used topics
    topics = m.get_recent_topics()
    print("Topics used:", topics)
    assert "AI agents" in topics
    
    # Log voice scores
    print("Logging voice scores...")
    m.save_voice_score(35, 30, 95)
    m.save_voice_score(20, 10, 60) # Below 65 to test flag
    
    scores = m.get_last_n_voice_scores(10)
    print("Recent scores:", scores)
    
    # Check post history
    history = m.get_post_history()
    print(f"Total posts in history: {len(history)}")
    
    # Update metrics
    if history:
        post_id = history[0]['id']
        m.update_post_performance(post_id, impressions=1000, likes=50, comments=10)
        
        # Verify
        updated_history = m.get_post_history()
        assert updated_history[0]['impressions'] == 1000
    
    print("\nMemory working!")

if __name__ == "__main__":
    test_memory()
