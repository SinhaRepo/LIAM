import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegram_bot.approval import request_approval
from modules.writer import generate_post
from rich.console import Console

console = Console()

def test_approval():
    console.print("[cyan]Generating a test post...[/cyan]")
    post = generate_post(
        topic="Testing the Telegram Bot Approval Flow",
        angle="Technical achievement",
        hook="Just finished wiring up my python-telegram-bot callbacks."
    )
    
    if post.startswith("Error"):
        console.print(f"[red]Error generating post: {post}[/red]")
        return
        
    console.print(f"[green]Post Generated! Sending to Telegram for approval...[/green]")
    console.print("[dim]Please check your phone and click a button![/dim]")
    
    # We won't use an image just to keep the test simple
    decision = request_approval(
        post_text=post,
        image_path=None,
        score=99,
        details="🎯 Topic: Telegram Bot Async Callbacks"
    )
    
    console.print(f"\n[bold magenta]User clicked:[/bold magenta] {decision}")
    
    if decision == "approve":
        console.print("[green]Awesome! Post was approved.[/green]")
    else:
        console.print(f"[yellow]Post was not approved. Action: {decision}[/yellow]")

if __name__ == "__main__":
    test_approval()
