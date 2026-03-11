import os
import sys
import json
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.research import get_trending_topics
from rich.console import Console

console = Console()

def test_research_module():
    console.print("[bold cyan]Testing Research Module...[/bold cyan]\n")
    
    start_time = time.time()
    result = get_trending_topics()
    end_time = time.time()
    
    console.print("\n[bold]Results JSON:[/bold]")
    console.print(json.dumps(result, indent=2))
    
    execution_time = end_time - start_time
    console.print(f"\n[bold]Execution Time:[/bold] {execution_time:.2f} seconds")
    
    if execution_time < 30:
        console.print("[bold green]Success! Target: < 30 seconds.[/bold green]")
    else:
        console.print("[bold red]Failed timing! Too slow.[/bold red]")

if __name__ == "__main__":
    test_research_module()
