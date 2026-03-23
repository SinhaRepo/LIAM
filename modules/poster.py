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
        if not self.access_token:
            return "testing_id_missing_token"
        resp = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json().get("sub", "testing_id_no_sub_found")
        console.print(f"[red]Error fetching profile: {resp.status_code}[/red]")
        return f"testing_id_auth_failed_{resp.status_code}"

    def perform_safety_checks(self, human_approved: bool):
        if not human_approved:
            raise SafetyError("Post was not approved by a human. Aborting.")
        now = datetime.now()
        if now.weekday() >= 5:
            raise SafetyError("Weekend posting is disabled.")
        today_str = now.strftime("%Y-%m-%d")
        posts_today = 0
        for post in self.memory.get_post_history(50):
            try:
                posted_at_str = post.get('posted_at')
                if not posted_at_str:
                    continue
                post_date = datetime.fromisoformat(posted_at_str)
                if post_date.strftime("%Y-%m-%d") == today_str:
                    posts_today += 1
                if now - post_date < timedelta(hours=3):
                    raise SafetyError(f"Last post was less than 3 hours ago ({now - post_date}).")
            except SafetyError:
                raise
            except (ValueError, TypeError):
                pass
        if posts_today >= self.max_posts_per_day:
            raise SafetyError(f"Daily post limit reached ({posts_today}/{self.max_posts_per_day}).")
        console.print("[green]✓ All safety checks passed.[/green]")
        return True

    def _make_post_request(self, payload: dict) -> requests.Response:
        """POST to LinkedIn with one 429 retry."""
        resp = requests.post("https://api.linkedin.com/v2/ugcPosts",
                             headers=self.headers, json=payload, timeout=30)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get('Retry-After', 60))
            console.print(f"[yellow]Rate limited. Retrying in {retry_after}s...[/yellow]")
            from telegram_bot.notifications import send_notification_sync, notify_error
            send_notification_sync(notify_error(f"LinkedIn rate limited. Retrying in {retry_after}s"))
            time.sleep(retry_after)
            resp = requests.post("https://api.linkedin.com/v2/ugcPosts",
                                 headers=self.headers, json=payload, timeout=30)
        return resp

    def _handle_response(self, resp: requests.Response, label: str) -> dict:
        if resp.status_code == 201:
            post_id = resp.headers.get("x-restli-id", "unknown")
            console.print(f"[green]Post published! ID: {post_id}[/green]")
            self._notify_telegram(label, f"https://www.linkedin.com/feed/update/{post_id}")
            return {"success": True, "post_id": post_id,
                    "url": f"https://www.linkedin.com/feed/update/{post_id}"}
        console.print(f"[red]Failed to post: {resp.text}[/red]")
        return {"success": False, "error": resp.text}

    def post_text_only(self, text: str, human_approved: bool = False, dry_run: bool = False) -> dict:
        try:
            self.perform_safety_checks(human_approved)
        except SafetyError as e:
            if dry_run and "Weekend posting" in str(e):
                console.print("[yellow]DRY RUN: Bypassing weekend check.[/yellow]")
            else:
                raise
        if dry_run:
            return {"success": True, "post_id": "urn:li:share:test12345", "url": "https://linkedin.com/test"}

        delay = random.randint(60, 480)
        console.print(f"[dim]Delaying {delay}s...[/dim]")
        time.sleep(delay)

        urn = f"urn:li:person:{self.get_profile_id()}"
        payload = {
            "author": urn, "lifecycleState": "PUBLISHED",
            "specificContent": {"com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE"
            }},
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        console.print("[cyan]Publishing text post...[/cyan]")
        return self._handle_response(self._make_post_request(payload), "Text Post")

    def upload_image(self, image_path: str) -> str:
        urn = f"urn:li:person:{self.get_profile_id()}"
        payload = {"registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": urn,
            "serviceRelationships": [{"relationshipType": "OWNER",
                                       "identifier": "urn:li:userGeneratedContent"}]
        }}
        console.print("[dim]Registering image upload...[/dim]")
        resp = requests.post("https://api.linkedin.com/v2/assets?action=registerUpload",
                             headers=self.headers, json=payload, timeout=30)
        if resp.status_code != 200:
            console.print(f"[red]Image registration failed: {resp.text}[/red]")
            return None
        data = resp.json()["value"]
        upload_url = data["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset_urn = data["asset"]
        console.print("[dim]Uploading image...[/dim]")
        with open(image_path, "rb") as f:
            up = requests.put(upload_url,
                              headers={"Authorization": f"Bearer {self.access_token}"},
                              data=f.read(), timeout=60)
        if up.status_code == 201:
            console.print("[green]Image uploaded.[/green]")
            return asset_urn
        console.print(f"[red]Image upload failed: {up.text}[/red]")
        return None

    def post_with_image(self, text: str, image_path: str, human_approved: bool = False, dry_run: bool = False) -> dict:
        try:
            self.perform_safety_checks(human_approved)
        except SafetyError as e:
            if dry_run and "Weekend posting" in str(e):
                console.print("[yellow]DRY RUN: Bypassing weekend check.[/yellow]")
            else:
                raise
        if dry_run:
            return {"success": True, "post_id": "urn:li:share:testimg123", "url": "https://linkedin.com/test"}

        delay = random.randint(60, 480)
        console.print(f"[dim]Delaying {delay}s...[/dim]")
        time.sleep(delay)

        asset_urn = self.upload_image(image_path)
        if not asset_urn:
            return {"success": False, "error": "Image upload failed"}

        urn = f"urn:li:person:{self.get_profile_id()}"
        payload = {
            "author": urn, "lifecycleState": "PUBLISHED",
            "specificContent": {"com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE",
                "media": [{"status": "READY",
                            "description": {"text": "LIAM post image"},
                            "media": asset_urn,
                            "title": {"text": "Post Image"}}]
            }},
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        return self._handle_response(self._make_post_request(payload), "Image Post")

    def _notify_telegram(self, label: str, url: str):
        try:
            from telegram_bot.notifications import notify_post_published, send_notification_sync
            send_notification_sync(notify_post_published(label, url))
        except Exception as e:
            console.print(f"[yellow]Could not send Telegram confirmation: {e}[/yellow]")
