from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

def display_welcome():
    title = Text("LinkedIn AI Agent v1.0 — Ansh Sinha", style="bold cyan")
    
    table = Table(show_header=False, expand=False, box=None)
    table.add_column("Key", style="bold green")
    table.add_column("Value")
    
    table.add_row("Status:", "RUNNING")
    table.add_row("Phase:", "Phase 7 - Fully Autonomous")
    
    panel = Panel(table, title=title, border_style="blue", padding=(1, 2))
    console.print(panel)
    console.print("\n")


