import os
import random
from modules.research import get_trending_topics
from modules.voice_scorer import generate_and_score_post
from modules.image_gen import generate_image
from telegram_bot.approval import request_approval
from modules.poster import Poster
from modules.memory import Memory
from rich.console import Console

console = Console()

ANGLES = [
    "Technical learning",
    "Lessons from failure",
    "Contrarian opinion",
    "Real project experience",
    "What I wish I knew earlier",
    "Behind the scenes of a real project",
]

HOOKS = [
    "Personal insight",
    "Surprising discovery",
    "Common mistake I made",
    "Honest take after shipping it",
    "Something I got wrong for years",
    "A question that changed how I think",
]


def _publish(post_text: str, image_path, topic: str, score: int, mem: Memory):
    """Post to LinkedIn and mark in DB. mem passed in — no extra instantiation."""
    poster = Poster()
    try:
        res = (poster.post_with_image(text=post_text, image_path=image_path, human_approved=True)
               if image_path else
               poster.post_text_only(text=post_text, human_approved=True))
        if not res.get("success"):
            raise Exception(res.get("error"))
        # save_post returns lastrowid — no extra get_last_post_id() query needed
        post_id = mem.save_post(topic=topic, content=post_text,
                                image_path=image_path, score=score, was_approved=True)
        mem.mark_as_posted(post_id)
        console.print("[green]✅ Posted to LinkedIn successfully![/green]")
    except Exception as e:
        msg = f"Failed to post to LinkedIn API: {e}. Saving draft."
        console.print(f"[red]{msg}[/red]")
        _safe_notify_error(msg)
        mem.save_post(topic=topic, content=post_text,
                      image_path=image_path, score=score, was_approved=True)


def agent_loop(user_prompt: str = None):
    console.print("\n[bold magenta]🧠 LIAM ReAct Loop Started[/bold magenta]")

    # Single Memory instance for entire loop run
    mem = Memory()

    # 1. Research or use provided topic
    topic_str = user_prompt
    if not topic_str:
        console.print("[cyan]THINK:[/cyan] Researching trending topics...")
        try:
            topic_str = get_trending_topics().get("recommended_topic")
            console.print(f"[green]OBSERVE:[/green] Chose topic: {topic_str}")
        except Exception as e:
            msg = f"Research phase failed: {e}"
            console.print(f"[red]{msg}[/red]")
            _safe_notify_error(msg)
            return
    else:
        console.print(f"[cyan]THINK:[/cyan] Using prompt: '{topic_str}'")

    # 2. Generate post
    console.print("[yellow]ACT:[/yellow] Generating post content...")
    try:
        angle, hook = random.choice(ANGLES), random.choice(HOOKS)
        console.print(f"[dim]Angle: {angle} | Hook: {hook}[/dim]")
        post, scores = generate_and_score_post(topic=topic_str, angle=angle, hook=hook)
        if not post or post.startswith("Error"):
            raise ValueError(f"Generation error: {post}")
    except Exception as e:
        msg = f"Groq generation failed: {e}."
        console.print(f"[red]{msg}[/red]")
        _safe_notify_error(msg)
        return

    # 3. Generate image
    image_path = None
    try:
        image_prompt = _generate_image_prompt(topic_str, post)
        console.print(f"[dim]Image prompt: {image_prompt}[/dim]")
        image_path = generate_image(image_prompt)
        if image_path:
            console.print("[green]OBSERVE:[/green] Image generated.")
    except Exception as e:
        console.print(f"[yellow]Image generation failed: {e}[/yellow]")

    # 4. Approval gate
    threshold = int(os.environ.get("VOICE_SCORE_THRESHOLD", 70))
    if scores["total_score"] < threshold:
        msg = (f"⚠️ *Post Skipped — Score Too Low*\n\nTopic: {topic_str}\n"
               f"Score: {scores['total_score']}/100 (threshold: {threshold})\n\n"
               "Consider updating `voice_profile/sample_posts.txt`.")
        console.print(f"[red]Score {scores['total_score']} below threshold. Aborting.[/red]")
        _safe_notify(msg)
    else:
        console.print("[cyan]THINK:[/cyan] Score good. Requesting Telegram approval.")
        decision = request_approval(post_text=post, image_path=image_path,
                                    score=scores["total_score"],
                                    details=f"Topic: {topic_str}")
        console.print(f"[green]OBSERVE:[/green] Decision: {decision}")

        if decision == "approve":
            _publish(post, image_path, topic_str, scores["total_score"], mem)

        elif decision == "regenerate":
            retry_count = getattr(agent_loop, "_retry_count", 0)
            if retry_count >= 2:
                console.print("[red]Max 3 regenerations reached.[/red]")
                _safe_notify("🔄 Max regenerations reached (3/3). Skipped.")
                agent_loop._retry_count = 0
                return
            agent_loop._retry_count = retry_count + 1
            agent_loop(topic_str)
            return

        elif decision == "edit":
            from telegram_bot.approval import request_text_reply
            edited_text = request_text_reply(timeout=600)
            if edited_text:
                _publish(edited_text, image_path, topic_str, scores["total_score"], mem)
            else:
                console.print("[yellow]Edit timed out.[/yellow]")
                _safe_notify("✏️ Edit timeout (10 min). Post skipped.")

        elif decision == "new_topic":
            _safe_notify("🎯 Got it! Finding a fresh trending topic...")
            agent_loop._retry_count = 0
            agent_loop()
            return

        elif decision in ("skip", "timeout"):
            label = "timeout after 1 hour" if decision == "timeout" else "skipped by you"
            _safe_notify(f"❌ Post {label}. See you next run! 👋")

        elif decision == "error":
            _safe_notify_error("Approval flow error. Check logs.")

        agent_loop._retry_count = 0

    # Voice drift check — reuse existing mem instance
    try:
        if mem.check_voice_drift():
            console.print("[bold red]🚨 VOICE DRIFT DETECTED[/bold red]")
            _safe_notify("⚠️ *Voice Drift Alert:* Last 10 posts averaging below 65/100. "
                         "Update `sample_posts.txt`.")
    except Exception:
        pass

    console.print("[bold magenta]🏁 LIAM ReAct Loop Completed[/bold magenta]\n")


def _generate_image_prompt(topic: str, post_text: str) -> str:
    from modules.writer import _get_groq_client  # reuse cached client
    try:
        resp = _get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    "Output ONE image generation prompt sentence. Visually specific — "
                    "objects, colors, composition, style. Professional, LinkedIn-appropriate. "
                    "No text, no faces. Just the prompt."
                )},
                {"role": "user", "content": (
                    f"Topic: {topic}\nPost: {post_text[:300]}\n"
                    "Write a single image prompt for this post."
                )},
            ],
            max_tokens=100, temperature=0.7,
        )
        return resp.choices[0].message.content.strip().strip('"')
    except Exception as e:
        console.print(f"[dim yellow]Image prompt fallback: {e}[/dim yellow]")
        return ("Minimalist flat design of interconnected nodes and data streams, "
                "dark background, blue and teal accents, professional tech aesthetic")


def _safe_notify_error(msg: str):
    try:
        from telegram_bot.notifications import notify_error, send_notification_sync
        send_notification_sync(notify_error(msg))
    except Exception:
        pass


def _safe_notify(msg: str):
    try:
        from telegram_bot.notifications import send_notification, send_notification_sync
        send_notification_sync(send_notification(msg))
    except Exception:
        pass
