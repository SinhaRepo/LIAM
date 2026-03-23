import os
import time
import requests
from rich.console import Console

console = Console()

_PROVIDERS = [
    {
        "name": "HuggingFace",
        "env": "HUGGINGFACE_TOKEN",
        "fn": lambda prompt, key: requests.post(
            "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
            headers={"Authorization": f"Bearer {key}"},
            json={"inputs": prompt},
            timeout=60
        ),
        "parse": lambda r: r.content,
    },
]


def generate_image(prompt: str, output_filename: str = None) -> str:
    """Try each provider in order. Returns saved path or None."""
    if not output_filename:
        os.makedirs("generated_images", exist_ok=True)
        output_filename = f"generated_images/post_img_{int(time.time())}.png"

    console.print(f"\n[cyan]Generating image...[/cyan]")
    console.print(f"[dim]Prompt: {prompt[:100]}...[/dim]")

    for p in _PROVIDERS:
        key = os.environ.get(p["env"])
        if not key:
            console.print(f"[yellow]{p['env']} not set, skipping {p['name']}[/yellow]")
            continue
        try:
            resp = p["fn"](prompt, key)
            if resp.status_code == 200:
                with open(output_filename, "wb") as f:
                    f.write(p["parse"](resp))
                console.print(f"[green]✓ Image generated via {p['name']}[/green]")
                return output_filename
            console.print(f"[red]{p['name']} Error {resp.status_code}: {resp.text[:100]}[/red]")
        except Exception as e:
            console.print(f"[red]{p['name']} failed: {e}[/red]")

    console.print("[bold red]❌ All image generation services failed[/bold red]")
    return None
