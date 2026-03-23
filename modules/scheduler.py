import os
import time
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from brain.react_loop import agent_loop
from modules.memory import Memory
from modules.poster import Poster
from telegram_bot.notifications import notify_daily_summary, notify_token_expiry
from rich.console import Console
from datetime import datetime

console = Console()

def research_and_draft():
    console.print("\n[bold blue]⏰ SCHEDULED JOB: Research & Draft (2.5Hr)[/bold blue]")
    t = threading.Thread(target=_run_agent_loop_safe)
    t.daemon = True
    t.start()

def _run_agent_loop_safe():
    try:
        agent_loop()
    except Exception as e:
        console.print(f"[red]Error in scheduled research_and_draft: {e}[/red]")

def morning_post_check():
    """Weekdays 8AM IST check for an approved unposted draft to publish."""
    console.print("\n[bold blue]⏰ SCHEDULED JOB: Morning Post Check[/bold blue]")
    try:
        m = Memory()
        console.print("[dim]Checking for approved drafts waiting to post...[/dim]")
        
        draft_posted = False
        drafts = m.get_unposted_approved_drafts(limit=5)
        
        for draft in drafts:
            p = Poster()
            if draft['image_path'] and os.path.exists(draft['image_path']):
                res = p.post_with_image(text=draft['content'], image_path=draft['image_path'], human_approved=True)
            else:
                res = p.post_text_only(text=draft['content'], human_approved=True)
            
            if res.get("success"):
                m.mark_as_posted(draft['id'])
                console.print(f"[green]Successfully published delayed draft ID {draft['id']}[/green]")
                draft_posted = True
            # Always break after first attempt — only post ONE draft per morning check
            break
        
        if not draft_posted:
             console.print("[dim]No valid approved drafts found to post.[/dim]")
             
        console.print("[green]Morning check completed.[/green]")
    except Exception as e:
        console.print(f"[red]Error in morning post check: {e}[/red]")

def daily_summary():
    console.print("\n[bold blue]⏰ SCHEDULED JOB: Daily Summary (9PM)[/bold blue]")
    try:
        m = Memory()
        history = m.get_post_history(10)
        today_str = datetime.now().strftime("%Y-%m-%d")
        count = sum(1 for p in history if p['date'].startswith(today_str))
        
        from telegram_bot.notifications import send_notification_sync
        send_notification_sync(notify_daily_summary(count))
    except Exception as e:
        console.print(f"[red]Error in daily summary: {e}[/red]")

def token_reminder():
    console.print("\n[bold blue]⏰ SCHEDULED JOB: Token Reminder (55 Days)[/bold blue]")
    try:
        from telegram_bot.notifications import send_notification_sync
        send_notification_sync(notify_token_expiry())
    except Exception as e:
        console.print(f"[red]Error sending token reminder: {e}[/red]")

def start_scheduler():
    console.print("[bold green]Starting LIAM Automated Scheduler...[/bold green]")
    scheduler = BackgroundScheduler()
    
    # 1. Research + Draft (every 2.5 hours)
    scheduler.add_job(research_and_draft, IntervalTrigger(hours=2.5), id='research_loop')
    
    # 2. Morning post window (weekdays 8AM IST)
    scheduler.add_job(morning_post_check, CronTrigger(day_of_week='mon-fri', hour=8, minute=0, timezone='Asia/Kolkata'), id='morning_post')
    
    # 3. Daily summary (9PM IST every day)
    scheduler.add_job(daily_summary, CronTrigger(hour=21, minute=0, timezone='Asia/Kolkata'), id='daily_summary')
    
    # 4. Token reminder (every 55 days)
    scheduler.add_job(token_reminder, IntervalTrigger(days=55), id='token_reminder')
    
    console.print("[green]Scheduler armed. Press Ctrl+C to exit.[/green]")
    scheduler.start()
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        console.print("\n[yellow]Scheduler gracefully stopped.[/yellow]")
