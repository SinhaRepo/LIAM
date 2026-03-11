import os
import asyncio
import threading
from dotenv import load_dotenv
from telegram import Bot
from telegram.ext import Application, CommandHandler
from rich.console import Console

console = Console()
load_dotenv()

# Shared state — one Application for everything
_shared_app: Application = None
_app_loop: asyncio.AbstractEventLoop = None
_app_ready = threading.Event()

def get_bot() -> Bot:
    """Returns an initialized Telegram Bot instance."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in .env")
    return Bot(token=token)

def get_chat_id() -> str:
    """Returns the configured admin chat ID."""
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID not found in .env")
    return chat_id

def get_shared_app() -> Application:
    """Returns the shared Application instance. Waits up to 15s for it to be ready."""
    _app_ready.wait(timeout=15)
    return _shared_app

def get_app_loop() -> asyncio.AbstractEventLoop:
    """Returns the event loop that the shared app runs in."""
    _app_ready.wait(timeout=15)
    return _app_loop

async def send_startup_message():
    """Sends a startup notification to the admin."""
    try:
        bot = get_bot()
        chat_id = get_chat_id()
        await bot.send_message(chat_id=chat_id, text="🤖 LIAM is online and ready!")
        console.print("[green]Successfully sent startup message to Telegram.[/green]")
    except Exception as e:
        console.print(f"[red]Failed to send startup message: {e}[/red]")

def start_command_bot():
    """
    Creates ONE shared Application instance.
    Registers all 7 command handlers.
    Runs polling in a background daemon thread forever.
    Exposes the app via get_shared_app() for approval.py to reuse.
    """
    global _shared_app, _app_loop

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        console.print("[yellow]TELEGRAM_BOT_TOKEN not set — command bot not started.[/yellow]")
        return

    from telegram_bot.commands import (
        start_command, status_command,
        history_command, report_command
    )

    def run_bot():
        global _shared_app, _app_loop

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _app_loop = loop

        async def _run():
            global _shared_app
            app = Application.builder().token(token).build()
            _shared_app = app

            app.add_handler(CommandHandler("start", start_command))
            app.add_handler(CommandHandler("status", status_command))
            app.add_handler(CommandHandler("history", history_command))
            app.add_handler(CommandHandler("report", report_command))

            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            _app_ready.set()  # signal: app is ready to use
            await send_startup_message()
            console.print("[green]✅ Command bot started — /status and all commands now active.[/green]")
            await asyncio.Event().wait()  # keep alive forever

        loop.run_until_complete(_run())

    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()
    _app_ready.wait(timeout=15)  # wait for app to be ready before returning
