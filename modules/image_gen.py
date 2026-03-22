import os
import time
import requests
from rich.console import Console

console = Console()

def generate_image(prompt: str, output_filename: str = None) -> str:
    """Generate image via HuggingFace FLUX.1-schnell. Returns path or None."""
    api_key = os.environ.get("HUGGINGFACE_TOKEN")
    if not api_key:
        console.print("[yellow]HUGGINGFACE_TOKEN not found in .env[/yellow]")
        return None

    if not output_filename:
        os.makedirs("generated_images", exist_ok=True)
        output_filename = f"generated_images/post_img_{int(time.time())}.png"

    console.print(f"\n[cyan]Generating image...[/cyan]")
    console.print(f"[dim]Prompt: {prompt[:100]}...[/dim]")

    try:
        response = requests.post(
            "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"inputs": prompt},
            timeout=60
        )
        if response.status_code == 200:
            with open(output_filename, "wb") as f:
                f.write(response.content)
            console.print("[green]✓ Image generated via HuggingFace[/green]")
            return output_filename
        console.print(f"[red]HuggingFace Error {response.status_code}: {response.text}[/red]")
    except Exception as e:
        console.print(f"[red]Image generation failed: {e}[/red]")
    return None
