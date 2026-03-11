import time
from datetime import datetime
from modules.research import get_trending_topics
from modules.voice_scorer import generate_and_score_post
from modules.image_gen import generate_image
from telegram_bot.approval import request_approval
from modules.poster import Poster
from modules.memory import Memory
from rich.console import Console

console = Console()

def agent_loop(user_prompt: str = None):
    console.print("\n[bold magenta]🧠 LIAM ReAct Loop Started[/bold magenta]")
    
    topic_str = user_prompt
    
    # 1. THINK & DECIDE: Research or Direct Prompt?
    if not topic_str:
        console.print("[cyan]THINK:[/cyan] No prompt provided. I need to research trending topics.")
        console.print("[yellow]ACT:[/yellow] Calling research module...")
        try:
            research_data = get_trending_topics()
            topic_str = research_data.get("recommended_topic")
            console.print(f"[green]OBSERVE:[/green] Chose topic: {topic_str}")
        except Exception as e:
            msg = f"Research phase failed: {e}"
            console.print(f"[red]{msg}[/red]")
            _safe_notify_error(msg)
            return
    else:
        console.print(f"[cyan]THINK:[/cyan] User provided explicit prompt: '{topic_str}'")

    # 2. ACT: Generate Post
    console.print("[yellow]ACT:[/yellow] Generating post content and scoring...")
    try:
        import random
        
        ANGLES = [
            "Technical learning",
            "Lessons from failure",
            "Contrarian opinion",
            "Tutorial walkthrough",
            "Real project experience",
            "What I wish I knew earlier",
            "Behind the scenes of a real project"
        ]
        
        HOOKS = [
            "Personal insight",
            "Surprising discovery",
            "Common mistake I made",
            "What nobody tells you",
            "Honest take after shipping it",
            "Something I got wrong for years",
            "A question that changed how I think"
        ]
        
        chosen_angle = random.choice(ANGLES)
        chosen_hook = random.choice(HOOKS)
        
        console.print(f"[dim]Angle: {chosen_angle} | Hook: {chosen_hook}[/dim]")
        
        post, scores = generate_and_score_post(
            topic=topic_str,
            angle=chosen_angle,
            hook=chosen_hook
        )
        if not post or post.startswith("Error"):
            raise ValueError(f"Generation returned an error: {post}")
    except Exception as e:
        msg = f"Groq generation failed: {e}. Retrying in 1 hour."
        console.print(f"[red]{msg}[/red]")
        _safe_notify_error(msg)
        return

    # 3. ACT: Generate Image
    console.print("[yellow]ACT:[/yellow] Generating supplementary image...")
    image_path = None
    try:
        image_prompt = f"Minimalist professional tech vector art representing {topic_str}"
        image_path = generate_image(image_prompt)
        console.print("[green]OBSERVE:[/green] Image generated successfully.")
    except Exception as e:
        console.print(f"[yellow]Warning: Image generation failed, falling back to text-only. Error: {e}[/yellow]")

    # 4. DECIDE: Approval
    if scores['total_score'] >= 70:
        console.print("[cyan]THINK:[/cyan] Score is good. Requesting human approval via Telegram.")
        decision = request_approval(post_text=post, image_path=image_path, score=scores['total_score'], details=f"Topic: {topic_str}")
        
        console.print(f"[green]OBSERVE:[/green] Human decision: {decision}")
        
        if decision == "approve":
            console.print("[yellow]ACT:[/yellow] Posting to LinkedIn...")
            poster = Poster()
            try:
                if image_path:
                    res = poster.post_with_image(text=post, image_path=image_path, human_approved=True)
                else:
                    res = poster.post_text_only(text=post, human_approved=True)
                    
                if not res.get("success"):
                    raise Exception(res.get("error"))
                    
                # Save to memory AFTER successful post with was_approved=True
                m = Memory()
                post_id = m.save_post(topic=topic_str, content=post, image_path=image_path, score=scores['total_score'], was_approved=True)
                post_id = m.get_last_post_id()
                if post_id:
                    m.mark_as_posted(post_id)
                console.print("[green]✅ Posted to LinkedIn successfully![/green]")
                    
            except Exception as e:
                msg = f"Failed to post to LinkedIn API: {e}. Saving draft to memory.db to retry next window."
                console.print(f"[red]{msg}[/red]")
                _safe_notify_error(msg)
                # Save as an approved draft that failed to post
                m = Memory()
                m.save_post(topic=topic_str, content=post, image_path=image_path, score=scores['total_score'], was_approved=True)

        elif decision == "regenerate":
            console.print("[yellow]ACT:[/yellow] Regenerating post with same topic...")
            retry_count = getattr(agent_loop, '_retry_count', 0)
            if retry_count >= 2:
                console.print("[red]Max 3 regenerations reached. Skipping.[/red]")
                _safe_notify("🔄 Max regenerations reached (3/3). Skipped.")
                agent_loop._retry_count = 0
                return
            agent_loop._retry_count = retry_count + 1
            console.print(f"[dim]Regeneration attempt {retry_count + 1}/3[/dim]")
            agent_loop(topic_str)
            return

        elif decision == "edit":
            console.print("[yellow]ACT:[/yellow] Waiting for your edited text on Telegram...")
            from telegram_bot.approval import request_text_reply
            edited_text = request_text_reply(timeout=600)
            if edited_text:
                console.print("[green]OBSERVE:[/green] Received edited text. Posting...")
                poster = Poster()
                try:
                    if image_path:
                        res = poster.post_with_image(text=edited_text, image_path=image_path, human_approved=True)
                    else:
                        res = poster.post_text_only(text=edited_text, human_approved=True)
                    if not res.get("success"):
                        raise Exception(res.get("error"))
                    m = Memory()
                    m.save_post(topic=topic_str, content=edited_text, image_path=image_path, score=scores['total_score'], was_approved=True)
                    post_id = m.get_last_post_id()
                    if post_id:
                        m.mark_as_posted(post_id)
                    console.print("[green]✅ Edited post published to LinkedIn![/green]")
                except Exception as e:
                    msg = f"Failed to post edited version: {e}. Saving draft."
                    console.print(f"[red]{msg}[/red]")
                    _safe_notify_error(msg)
                    m = Memory()
                    m.save_post(topic=topic_str, content=edited_text, image_path=image_path, score=scores['total_score'], was_approved=True)
            else:
                console.print("[yellow]Edit timed out after 10 minutes. Skipping.[/yellow]")
                _safe_notify("✏️ Edit timeout (10 min). Post skipped.")

        elif decision == "new_topic":
            console.print("[yellow]ACT:[/yellow] Researching a completely new topic...")
            _safe_notify("🎯 Got it! Finding a fresh trending topic for you...")
            agent_loop._retry_count = 0
            agent_loop()  # no topic = auto-research
            return

        elif decision in ("skip", "timeout"):
            msg = "timeout after 1 hour" if decision == "timeout" else "skipped by you"
            console.print(f"[yellow]ACT:[/yellow] Post {msg}.")
            _safe_notify(f"❌ Post skipped ({decision}). See you next run! 👋")

        elif decision == "error":
            console.print("[red]Telegram approval error. Post not published.[/red]")
            _safe_notify_error("Approval flow error. Check logs.")

        # Always reset retry counter after terminal decision
        agent_loop._retry_count = 0
    else:
        msg = (
            f"⚠️ *Post Skipped — Score Too Low*\n\n"
            f"Topic: {topic_str}\n"
            f"Best score after 3 attempts: {scores['total_score']}/100\n"
            f"Threshold: 70/100\n\n"
            f"Consider updating `voice_profile/sample_posts.txt` "
            f"with your recent posts to improve scoring."
        )
        console.print(f"[red]THINK:[/red] Score {scores['total_score']} is too low after 3 attempts. Aborting.")
        _safe_notify(msg)
        
    # Phase 6 Fix: Auto voice drift warning
    try:
        if Memory().check_voice_drift():
            console.print("[bold red]🚨 VOICE DRIFT DETECTED: Average score < 65.[/bold red]")
            _safe_notify("⚠️ *Voice Drift Alert:* Your last 10 posts are averaging below 65/100 authenticity score. Consider updating your `sample_posts.txt`.")
    except Exception as e:
        pass
        
    console.print("[bold magenta]🏁 LIAM ReAct Loop Completed[/bold magenta]\n")

def _safe_notify_error(msg: str):
    """Safely dispatches async notification from synchronous execution."""
    try:
        from telegram_bot.notifications import notify_error, send_notification_sync
        send_notification_sync(notify_error(msg))
    except Exception as e:
        console.print(f"[red]Could not notify Telegram locally about error: {e}[/red]")

def _safe_notify(msg: str):
    """Safely dispatches an informational async notification from synchronous execution."""
    try:
        from telegram_bot.notifications import send_notification, send_notification_sync
        send_notification_sync(send_notification(msg))
    except Exception as e:
        console.print(f"[red]Could not send Telegram notification: {e}[/red]")
