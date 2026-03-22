import os
import asyncio
from telegram_bot.bot import get_bot, get_chat_id
from rich.console import Console

console = Console()

async def send_notification(text: str, parse_mode="Markdown"):
    """Generic async helper to send a notification message."""
    try:
        bot = get_bot()
        chat_id = get_chat_id()
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
    except RuntimeError as e:
        if "interpreter shutdown" in str(e) or "cannot schedule" in str(e):
            pass  # silently ignore — process is exiting, notification is non-critical
        else:
            console.print(f"[red]Failed to send notification: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to send notification: {e}[/red]")

async def notify_post_published(topic: str, linkedin_url: str = None):
    """Notification format for successfully published post."""
    url_text = f"URL: {linkedin_url}" if linkedin_url else ""
    message = f"✅ *Post Successfully Published!*\n\nTopic: {topic}\n{url_text}"
    await send_notification(message)

async def notify_daily_summary(posts_count: int, new_followers: int = 0):
    """Notification for 9PM daily summary."""
    message = f"🌙 *Daily Summary*\n\nPosts made today: {posts_count}\nNew followers tracked: {new_followers}\n\nGoodnight! 🤖"
    await send_notification(message)


async def notify_token_expiry(days_left: int = 5):
    """Notification reminding Ansh to refresh LinkedIn tokens."""
    message = (
        "⚠️ *LIAM Token Reminder*\n\n"
        f"LinkedIn access token expires in ~{days_left} days.\n"
        "Run: `python tools/get_token.py`\n"
        "Takes 30 seconds. Don't forget! 🔑"
    )
    await send_notification(message)

async def notify_error(error_details: str):
    """Notification for critical system failures."""
    message = f"🚨 SYSTEM ERROR\n\n{error_details}"
    await send_notification(message, parse_mode=None)

def send_notification_sync(coro):
    """
    Safely dispatches an async notification coroutine from a synchronous execution context.
    Creates a new event loop in a background thread to ensure it runs to completion 
    without blocking or being cancelled by the main thread cleanly exiting.
    """
    import threading
    
    def run_in_thread(coro_obj):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro_obj)
        except Exception as e:
            console.print(f"[red]Background notification error: {e}[/red]")
        finally:
            loop.close()
            
    thread = threading.Thread(target=run_in_thread, args=(coro,))
    thread.daemon = False  # Allows it to finish if main exits quickly
    thread.start()
