import os
import time
import random
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from modules.memory import Memory
from rich.console import Console

console = Console()
load_dotenv()

class SafetyError(Exception):
    pass

class Poster:
    def __init__(self):
        self.access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        self.memory = Memory()
        self.max_posts_per_day = int(os.environ.get("MAX_POSTS_PER_DAY", 2))

    def get_profile_id(self) -> str:
        """GET https://api.linkedin.com/v2/me replacing old openid due to w_member_social bounds"""
        if not self.access_token:
            console.print("[yellow]LINKEDIN_ACCESS_TOKEN not found in .env[/yellow]")
            return "testing_id_missing_token"
            
        url = "https://api.linkedin.com/v2/userinfo"
        response = requests.get(url, headers={"Authorization": f"Bearer {self.access_token}"}, timeout=30)
        if response.status_code == 200:
            return response.json().get("sub", "testing_id_no_sub_found")
        else:
            console.print(f"[red]Error fetching profile: {response.status_code} {response.text}[/red]")
            return f"testing_id_auth_failed_{response.status_code}"

    def perform_safety_checks(self, human_approved: bool):
        if not human_approved:
            raise SafetyError("Post was not approved by a human. Aborting.")
            
        now = datetime.now()
        
        # Is today a weekday?
        if now.weekday() >= 5: # 5=Sat, 6=Sun
            # To allow testing on weekend, we just print a warning if we bypass this in dry_run, but for real we raise:
            raise SafetyError("Weekend posting is disabled.")
            
        # Get history
        history = self.memory.get_post_history(50)
        
        today_str = now.strftime("%Y-%m-%d")
        posts_today = 0
        
        for post in history:
            try:
                posted_at_str = post.get('posted_at')
                if not posted_at_str:
                    continue # Skip unposted drafts entirely for safety calculations
                    
                post_date = datetime.fromisoformat(posted_at_str)
                if post_date.strftime("%Y-%m-%d") == today_str:
                    posts_today += 1
                    
                # Check if last post was < 4 hours ago
                time_diff = now - post_date
                if time_diff < timedelta(hours=4):
                    raise SafetyError(f"Last post was less than 4 hours ago ({time_diff}).")
            except SafetyError:
                raise  # re-raise so caller actually sees it
            except (ValueError, TypeError):
                pass
                
        if posts_today >= self.max_posts_per_day:
            raise SafetyError(f"Daily post limit reached ({posts_today}/{self.max_posts_per_day}).")
            
        console.print("[green]✓ All safety checks passed.[/green]")
        return True

    def post_text_only(self, text: str, human_approved: bool = False, dry_run: bool = False) -> dict:
        # For testing purposes, if dry_run, we can handle the exception gracefully or just run checks
        try:
            self.perform_safety_checks(human_approved)
        except SafetyError as e:
            if dry_run and "Weekend posting" in str(e):
                console.print("[yellow]DRY RUN: Bypassing Weekend posting limit for testing.[/yellow]")
            else:
                raise
                
        if dry_run:
            console.print("[yellow]DRY RUN: Skipping randomized delay and API call.[/yellow]")
            return {"success": True, "post_id": "urn:li:share:test12345", "url": "https://linkedin.com/test"}
            
        # Randomized human-like delay
        delay = random.randint(60, 480)
        console.print(f"[dim]Adding human-like delay of {delay} seconds...[/dim]")
        time.sleep(delay)
        
        profile_id = self.get_profile_id()
        urn = f"urn:li:person:{profile_id}"
        
        url = "https://api.linkedin.com/v2/ugcPosts"
        payload = {
            "author": urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        console.print("[cyan]Publishing text post to LinkedIn...[/cyan]")
        resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        # Handle 429 rate limiting
        if resp.status_code == 429:
            retry_after = int(resp.headers.get('Retry-After', 60))
            console.print(f"[yellow]LinkedIn rate limited. Retrying in {retry_after}s...[/yellow]")
            from telegram_bot.notifications import send_notification_sync, notify_error
            send_notification_sync(notify_error(f"LinkedIn rate limited. Retrying in {retry_after}s"))
            time.sleep(retry_after)
            resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        if resp.status_code == 201:
            post_id = resp.headers.get("x-restli-id", "unknown")
            console.print(f"[green]Post published! ID: {post_id}[/green]")
            self._notify_telegram("Text Post", f"https://www.linkedin.com/feed/update/{post_id}")
            return {"success": True, "post_id": post_id, "url": f"https://www.linkedin.com/feed/update/{post_id}"}
        else:
            console.print(f"[red]Failed to post: {resp.text}[/red]")
            return {"success": False, "error": resp.text}

    def upload_image(self, image_path: str) -> str:
        profile_id = self.get_profile_id()
        urn = f"urn:li:person:{profile_id}"
        register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
        
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": urn,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }
                ]
            }
        }
        
        console.print("[dim]Registering image upload with LinkedIn...[/dim]")
        resp = requests.post(register_url, headers=self.headers, json=register_payload, timeout=30)
        if resp.status_code != 200:
            console.print(f"[red]Image registration failed: {resp.text}[/red]")
            return None
            
        data = resp.json()
        upload_url = data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset_urn = data["value"]["asset"]
        
        console.print("[dim]Uploading image bytes...[/dim]")
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            
        upload_headers = {"Authorization": f"Bearer {self.access_token}"}
        upload_resp = requests.put(upload_url, headers=upload_headers, data=image_bytes, timeout=60) # Longer timeout for image upload
        
        if upload_resp.status_code == 201:
            console.print("[green]Image uploaded successfully![/green]")
            return asset_urn
        else:
            console.print(f"[red]Image byte upload failed: {upload_resp.text}[/red]")
            return None

    def post_with_image(self, text: str, image_path: str, human_approved: bool = False, dry_run: bool = False) -> dict:
        try:
            self.perform_safety_checks(human_approved)
        except SafetyError as e:
            if dry_run and "Weekend posting" in str(e):
                console.print("[yellow]DRY RUN: Bypassing Weekend posting limit for testing.[/yellow]")
            else:
                raise
                
        if dry_run:
            console.print("[yellow]DRY RUN: Skipping image upload, delay, and API logic.[/yellow]")
            return {"success": True, "post_id": "urn:li:share:testimg123", "url": "https://linkedin.com/test"}
            
        delay = random.randint(60, 480)
        console.print(f"[dim]Adding human-like delay of {delay} seconds...[/dim]")
        time.sleep(delay)
        
        asset_urn = self.upload_image(image_path)
        if not asset_urn:
            return {"success": False, "error": "Image upload failed"}
            
        profile_id = self.get_profile_id()
        urn = f"urn:li:person:{profile_id}"
        
        url = "https://api.linkedin.com/v2/ugcPosts"
        payload = {
            "author": urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {"text": "Image generated for LIAM post"},
                            "media": asset_urn,
                            "title": {"text": "Post Image"}
                        }
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        # Handle 429 rate limiting
        if resp.status_code == 429:
            retry_after = int(resp.headers.get('Retry-After', 60))
            console.print(f"[yellow]LinkedIn rate limited. Retrying in {retry_after}s...[/yellow]")
            from telegram_bot.notifications import send_notification_sync, notify_error
            send_notification_sync(notify_error(f"LinkedIn rate limited. Retrying in {retry_after}s"))
            time.sleep(retry_after)
            resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        if resp.status_code == 201:
            post_id = resp.headers.get("x-restli-id", "unknown")
            console.print(f"[green]Post published! ID: {post_id}[/green]")
            self._notify_telegram("Image Post", f"https://www.linkedin.com/feed/update/{post_id}")
            return {"success": True, "post_id": post_id, "url": f"https://www.linkedin.com/feed/update/{post_id}"}
        else:
            console.print(f"[red]Failed to post: {resp.text}[/red]")
            return {"success": False, "error": resp.text}
            
    def _notify_telegram(self, topic: str, url: str):
        try:
            from telegram_bot.notifications import notify_post_published, send_notification_sync
            send_notification_sync(notify_post_published(topic, url))
        except Exception as e:
            console.print(f"[yellow]Could not send telegram confirmation: {e}[/yellow]")
