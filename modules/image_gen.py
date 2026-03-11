import os
import time
import requests
from dotenv import load_dotenv
from rich.console import Console

console = Console()
load_dotenv()

def generate_image_stability(prompt: str, output_path: str) -> bool:
    """Generate image using Stability AI REST API (Primary)"""
    api_key = os.environ.get("STABILITY_API_KEY")
    if not api_key:
        console.print("[yellow]STABILITY_API_KEY not found in .env[/yellow]")
        return False
        
    console.print(f"[dim]Attempting generation with Stability AI API...[/dim]")
    url = "https://api.stability.ai/v2beta/stable-image/generate/core"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "image/*"
    }
    
    # Multipart form data format required by Stability v2beta API
    files = {
        "prompt": (None, prompt),
        "output_format": (None, "png"),
        # 16:9 aspect ratio is good for LinkedIn
        "aspect_ratio": (None, "16:9")
    }
    
    try:
        response = requests.post(url, headers=headers, files=files, timeout=30)
        
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            console.print("[green]✓ Image generated successfully via Stability AI[/green]")
            return True
        else:
            console.print(f"[red]Stability API Error {response.status_code}: {response.text}[/red]")
            return False
            
    except Exception as e:
        console.print(f"[red]Exception calling Stability API: {str(e)}[/red]")
        return False

def generate_image_huggingface(prompt: str, output_path: str) -> bool:
    """Generate image using HuggingFace Inference API (Fallback)"""
    api_key = os.environ.get("HUGGINGFACE_TOKEN")
    if not api_key:
        console.print("[yellow]HUGGINGFACE_TOKEN not found in .env[/yellow]")
        return False
        
    console.print(f"[dim]Attempting fallback generation with HuggingFace FLUX.1-schnell...[/dim]")
    url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "inputs": prompt,
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            console.print("[green]✓ Image generated successfully via HuggingFace[/green]")
            return True
        else:
            console.print(f"[red]HuggingFace API Error {response.status_code}: {response.text}[/red]")
            return False
            
    except Exception as e:
        console.print(f"[red]Exception calling HuggingFace API: {str(e)}[/red]")
        return False

def generate_image(prompt: str, output_filename: str = None) -> str:
    """
    Generate an image from a prompt, trying Stability first and HuggingFace as fallback.
    Returns the path to the saved image, or None if failed.
    """
    if not output_filename:
        timestamp = int(time.time())
        # Ensure output directory exists before writing
        os.makedirs("generated_images", exist_ok=True)
        output_filename = f"generated_images/post_img_{timestamp}.png"
        
    console.print(f"\n[cyan]🖼️  Generating Image...[/cyan]")
    console.print(f"[dim]Prompt: {prompt[:100]}...[/dim]")
    
    # Try primary service
    if generate_image_stability(prompt, output_filename):
        return output_filename
        
    # Try fallback service
    console.print("[yellow]Primary service failed, trying fallback...[/yellow]")
    if generate_image_huggingface(prompt, output_filename):
        return output_filename
        
    console.print("[bold red]❌ All image generation services failed[/bold red]")
    return None
