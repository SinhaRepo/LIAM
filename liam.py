import argparse
import sys
from cli.interface import display_welcome
from brain.react_loop import agent_loop
from modules.memory import Memory
from modules.scheduler import start_scheduler
from rich.console import Console

console = Console()

def main():
    from telegram_bot.bot import start_command_bot
    start_command_bot()  # commands work in ALL modes now
    
    parser = argparse.ArgumentParser(description="LIAM — LinkedIn Intelligent Autonomous Manager")
    parser.add_argument("topic", nargs="*", help="Specific topic to write about (e.g. 'write a post about Python decorators')")
    parser.add_argument("--schedule", action="store_true", help="Run agent on automated schedule (Phase 7)")
    parser.add_argument("--status", action="store_true", help="Check agent status")
    parser.add_argument("--history", action="store_true", help="Shows last 10 posts")
    
    args = parser.parse_args()
    
    display_welcome()
    
    if args.status:
        console.print("\n[bold green]STATUS: LIAM is Fully Autonomous (Phase 7)[/bold green]")
        console.print("[dim]Modules Active: Writer, Research, Scheduler, Memory, Telegram, Poster.[/dim]")
        sys.exit(0)
        
    if args.history:
        m = Memory()
        history = m.get_post_history(10)
        console.print("\n[bold cyan]=== LAST 10 POSTS ===[/bold cyan]")
        if not history:
            console.print("No posts found in memory.")
        for post in history:
            date_str = post['date'][:10]
            score = post['confidence_score']
            topic = post['topic']
            approved = "✅" if post['was_approved'] else "❌"
            console.print(f"[dim]{date_str}[/dim] | Score: {score} | Approved: {approved} | Topic: {topic}")
        sys.exit(0)
        
    if args.schedule:
        start_scheduler()
        sys.exit(0)
        
    if args.topic:
        topic_text = " ".join(args.topic)
        if topic_text.lower().startswith("write a post about"):
            topic_text = topic_text[18:].strip()
            
        console.print(f"[dim]Triggering ReAct loop for explicit topic: '{topic_text}'...[/dim]\n")
        agent_loop(topic_text)
    else:
        # Check for unposted drafts first (Queue Bypass Fix)
        from modules.scheduler import morning_post_check
        m = Memory()
        drafts = m.get_drafts_count()
        if drafts > 0:
            console.print(f"\n[yellow]LIAM found {drafts} unposted approved draft(s). Attempting to publish backlog first...[/yellow]")
            morning_post_check()
            return
            
        # ReAct loop defaults to researching an entirely new topic autonomously
        console.print("[dim]Triggering autonomous ReAct loop...[/dim]\n")
        agent_loop()

if __name__ == "__main__":
    main()
    import time
    time.sleep(2)  # grace period for pending Telegram notifications to flush
