import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.poster import Poster, SafetyError
from rich.console import Console

console = Console()

def test_safety_and_profile():
    console.print("\n[bold cyan]Testing Poster Module[/bold cyan]\n")
    p = Poster()
    
    # Test 1: get_profile_id()
    console.print("[bold]1. Testing get_profile_id()[/bold]")
    profile = p.get_profile_id()
    console.print(f"LinkedIn Profile ID: {profile}\n")
    
    # Test 2: Safety Checks (Unapproved should raise error)
    console.print("[bold]2. Testing human_approved=False[/bold]")
    try:
        p.post_text_only("Hello World", human_approved=False, dry_run=True)
        console.print("[red]Failed: Did not catch unapproved post![/red]")
    except SafetyError as e:
        console.print(f"[green]Caught expected SafetyError: {e}[/green]\n")
        
    # Test 3: Valid post (dry run)
    console.print("[bold]3. Testing human_approved=True (Dry Run)[/bold]")
    try:
        # Note: if running on weekend this will bypass because dry_run=True captures and allows it via console warning
        res = p.post_text_only("Testing LIAM's automated posting capabilities.", human_approved=True, dry_run=True)
        console.print(f"Result: {res}")
        if res.get("success"):
            console.print("[green]Dry run successful![/green]\n")
    except SafetyError as e:
        console.print(f"[yellow]Safety check caught something: {e}[/yellow]\n")

if __name__ == "__main__":
    test_safety_and_profile()
