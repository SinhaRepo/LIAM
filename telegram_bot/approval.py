import os
import asyncio
import threading
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram_bot.bot import get_shared_app, get_app_loop, get_chat_id
from rich.console import Console

console = Console()

def get_approval_keyboard() -> InlineKeyboardMarkup:
    """Creates the inline keyboard for post approval."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data="approve"),
            InlineKeyboardButton("✏️ Edit Post", callback_data="edit")
        ],
        [
            InlineKeyboardButton("🔄 Regenerate", callback_data="regenerate"),
            InlineKeyboardButton("🎯 New Topic", callback_data="new_topic")
        ],
        [
            InlineKeyboardButton("❌ Skip Today", callback_data="skip")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def request_approval(post_text: str, image_path: str = None,
                     score: int = None, details: str = None) -> str:
    """
    Sends approval message and waits for button tap.
    Uses the shared Application — no new polling started.
    Uses threading.Event for safe cross-thread communication.
    Timeout: 1 hour.
    """
    result = {'decision': None}
    done_event = threading.Event()
    ADMIN_ID = int(os.environ.get("TELEGRAM_CHAT_ID", 0))
    chat_id = get_chat_id()

    app = get_shared_app()
    loop = get_app_loop()

    if app is None or loop is None:
        console.print("[red]Shared app not available. Cannot request approval.[/red]")
        return "error"

    action_map = {
        "approve": "✅ Post Approved!",
        "edit": "✏️ Edit mode — send your text.",
        "regenerate": "🔄 Regenerating...",
        "new_topic": "🎯 Choosing new topic...",
        "skip": "❌ Skipped for today."
    }

    # We need a reference to the handler so we can remove it later
    callback_handler = None

    async def do_send_and_register():
        """Runs inside the bot's event loop thread."""
        nonlocal callback_handler
        try:
            # Build message
            message = "🤖 *LinkedIn Agent — Post Ready*\n\n"
            if details:
                message += f"{details}\n"
            if score:
                message += f"📈 *Confidence Score:* {score}/100\n"
            message += f"\n─────────────────────────────\n\n✍️ *Draft Post:*\n\n{post_text}\n\n─────────────────────────────"

            # Send message with buttons
            if image_path and os.path.exists(image_path):
                if len(message) <= 1000:
                    with open(image_path, "rb") as photo:
                        await app.bot.send_photo(
                            chat_id=chat_id, photo=photo,
                            caption=message, parse_mode="Markdown",
                            reply_markup=get_approval_keyboard()
                        )
                else:
                    with open(image_path, "rb") as photo:
                        await app.bot.send_photo(chat_id=chat_id, photo=photo)
                    await app.bot.send_message(
                        chat_id=chat_id, text=message[:4000],
                        parse_mode="Markdown",
                        reply_markup=get_approval_keyboard()
                    )
            else:
                await app.bot.send_message(
                    chat_id=chat_id, text=message[:4000],
                    parse_mode="Markdown",
                    reply_markup=get_approval_keyboard()
                )

            console.print("[cyan]Waiting for approval on Telegram...[/cyan]")

            # Register callback handler on SHARED app (no new polling!)
            async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
                query = update.callback_query
                if query.from_user.id != ADMIN_ID:
                    await query.answer("Unauthorized.")
                    return
                await query.answer()
                decision = query.data
                await query.edit_message_reply_markup(reply_markup=None)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Action received: {action_map.get(decision, 'Acknowledged.')}"
                )
                result['decision'] = decision
                app.remove_handler(callback_handler, group=10)
                done_event.set()

            # Use group=10 to avoid interfering with command handlers (group=0)
            callback_handler = CallbackQueryHandler(button_callback)
            app.add_handler(callback_handler, group=10)

        except Exception as e:
            import traceback
            console.print(f"[red]Error setting up approval: {e}[/red]")
            traceback.print_exc()
            done_event.set()

    # Schedule the send+register in the bot's event loop
    asyncio.run_coroutine_threadsafe(do_send_and_register(), loop)

    # Wait in main thread (with 1 hour timeout)
    timed_out = not done_event.wait(timeout=3600)

    if timed_out:
        # Clean up the handler if it was registered
        if callback_handler is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    _remove_handler_async(app, callback_handler, 10), loop
                ).result(timeout=5)
            except Exception:
                pass
        console.print("[yellow]Approval timed out after 1 hour.[/yellow]")
        return "timeout"

    if result['decision'] is None:
        return "error"

    return result['decision']


def request_text_reply(timeout: int = 600) -> str:
    """
    After Edit button tap, waits for admin to type and send edited post.
    Uses the shared Application — no new polling.
    Timeout: 10 minutes (600 seconds).
    Returns the text string or None on timeout.
    """
    result = {'text': None}
    done_event = threading.Event()
    ADMIN_ID = int(os.environ.get("TELEGRAM_CHAT_ID", 0))
    chat_id = get_chat_id()

    app = get_shared_app()
    loop = get_app_loop()

    if app is None or loop is None:
        return None

    msg_handler = None

    async def do_setup():
        nonlocal msg_handler
        await app.bot.send_message(
            chat_id=chat_id,
            text=(
                "✏️ *Edit Mode Activated*\n\n"
                "Type your edited post and send it as a message.\n"
                "I'll post your exact version to LinkedIn.\n\n"
                "⏳ You have 10 minutes."
            ),
            parse_mode="Markdown"
        )

        async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user.id != ADMIN_ID:
                return
            result['text'] = update.message.text
            app.remove_handler(msg_handler, group=11)
            done_event.set()

        msg_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
        app.add_handler(msg_handler, group=11)

    asyncio.run_coroutine_threadsafe(do_setup(), loop)

    timed_out = not done_event.wait(timeout=timeout)

    if timed_out and msg_handler is not None:
        try:
            asyncio.run_coroutine_threadsafe(
                _remove_handler_async(app, msg_handler, 11), loop
            ).result(timeout=5)
        except Exception:
            pass

    return result['text']


async def _remove_handler_async(app, handler, group):
    """Helper to remove a handler from the shared app in its event loop."""
    try:
        app.remove_handler(handler, group=group)
    except Exception:
        pass
