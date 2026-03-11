import os
import sys

# Add parent directory to path to allow importing modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.image_gen import generate_image
from rich.console import Console

console = Console()

def test_image_generation():
    console.print("[bold cyan]Testing Image Generation APIs[/bold cyan]\n")
    
    prompt = "A sleek data server rack glowing with blue and purple neon lights, high quality, professional photography, 4k"
    
    console.print(f"[bold]Prompt:[/bold] {prompt}\n")
    
    output_path = generate_image(prompt)
    
    if output_path and os.path.exists(output_path):
        console.print(f"\n[bold green]Success![/bold green] Image saved at: {output_path}")
        size_kb = os.path.getsize(output_path) / 1024
        console.print(f"File size: {size_kb:.1f} KB")
        assert True
    else:
        console.print("\n[bold red]Failed![/bold red] Could not generate or save image.")
        assert False, "Image generation failed"

if __name__ == "__main__":
    test_image_generation()
