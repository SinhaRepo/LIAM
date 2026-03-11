import os
from telegram import Update
from telegram.ext import ContextTypes
from modules.memory import Memory

async def _check_auth(update: Update) -> bool:
    """Returns False and replies 'Unauthorized.' if user is not the admin."""
    admin_id = int(os.environ.get("TELEGRAM_CHAT_ID", 0))
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Unauthorized.")
        return False
    return True

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start"""
    if not await _check_auth(update):
        return
    await update.message.reply_text(
        "🤖 *Welcome to LIAM (LinkedIn Intelligent Autonomous Manager)*\n\n"
        "I am currently online and ready to manage your LinkedIn.\n"
        "Available commands:\n"
        "/status - Current agent status\n"
        "/history - Last 5 published posts\n"
        "/report - Performance summary and voice drift",
        parse_mode="Markdown"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /status"""
    if not await _check_auth(update):
        return
    try:
        m = Memory()
        recent = m.get_post_history(1)
        last_post_time = recent[0]['date'][:16].replace('T', ' ') if recent else "Never"
        drafts = m.get_drafts_count()
        posts_today = m.get_posts_today_count()
    except Exception:
        last_post_time = "Unknown"
        drafts = 0
        posts_today = 0
        
    await update.message.reply_text(
        "📊 *LIAM Status*\n\n"
        "🟢 Agent: Active (GitHub Actions)\n"
        f"📅 Last Post: {last_post_time or 'No posts yet'}\n"
        f"📬 Posts Today: {posts_today}/2\n"
        f"📥 Pending Drafts: {drafts}",
        parse_mode="Markdown"
    )



async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /history"""
    if not await _check_auth(update):
        return
    try:
        m = Memory()
        history = m.get_post_history(5)
        
        if not history:
            await update.message.reply_text("No recent posts found in history.")
            return
            
        text = "📜 *Recent Post History:*\n\n"
        for post in history:
            text += f"▪️ *{post['date'][:10]}* - {post['topic']}\n"
            text += f"   _Score:_ {post['confidence_score']} | _Approved:_ {bool(post['was_approved'])}\n\n"
            
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error reading history: {e}")



async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /report"""
    if not await _check_auth(update):
        return
    try:
        m = Memory()
        drift = m.check_voice_drift()
        
        text = "📈 *Weekly Performance Summary:*\n\n"
        text += "Posts configured: 2/day\n"
        text += f"Voice Drift Warning: {'[RED] YES' if drift else 'NO'}\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error fetching report: {e}")

