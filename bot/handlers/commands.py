"""
Command Handlers
Basic bot commands (start, help, status, menu).
"""

import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.config import logger, ALLOWED_CHAT_IDS, WATCH_FOLDER
from bot.utils import escape_markdown_v2, is_authorized, get_main_menu_keyboard, get_back_keyboard
from bot.services import get_rss_url


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name or "User"

    logger.info(f"Start command received from chat ID: {chat_id}")

    is_auth = is_authorized(chat_id)
    auth_emoji = "✅" if is_auth else "⚠️"

    welcome_message = (
        f"╔═══════════════════════╗\n"
        f"   🤖 *SEND TORRENT BOT*   \n"
        f"╚═══════════════════════╝\n\n"
        f"👋 Welcome *{user_name}*\\!\n\n"
        f"I help you manage torrents remotely\\.\n"
        f"Just send me a `.torrent` file and I'll\n"
        f"handle the rest\\! 🚀\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"  {auth_emoji} *Authorization Status*\n"
        f"     {'`AUTHORIZED`' if is_auth else '`NOT AUTHORIZED`'}\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"💡 Use the menu below to get started\\!"
    )

    await update.message.reply_text(
        welcome_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard(has_rss=bool(get_rss_url(chat_id)))
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_message = (
        "╔═══════════════════════╗\n"
        "       📖 *HELP GUIDE*       \n"
        "╚═══════════════════════╝\n\n"
        "*Available Commands:*\n\n"
        "🏠 `/start` \\- Main menu \\& welcome\n"
        "❓ `/help` \\- Show this help guide\n"
        "📊 `/status` \\- Check bot status\n"
        "🔍 `/menu` \\- Show interactive menu\n"
        "📡 `/setrss <URL>` \\- Set RSS feed\n"
        "🔎 `/browse` \\- Browse RSS feed\n"
        "🗑️ `/clearrss` \\- Remove RSS feed\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Quick Actions:*\n\n"
        "• Send any `.torrent` file\n"
        "• Use the menu buttons\n"
        "• Check your authorization\n"
        "• Browse your RSS feed\n\n"
        "💡 *Tip:* Keep your chat ID safe\\!"
    )

    await update.message.reply_text(
        help_message, parse_mode="MarkdownV2", reply_markup=get_back_keyboard()
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    chat_id = update.effective_chat.id
    is_auth = is_authorized(chat_id)

    auth_icon = "✅" if is_auth else "❌"
    auth_text = "AUTHORIZED" if is_auth else "NOT AUTHORIZED"

    # Count torrent files in watch folder
    try:
        torrent_count = len([f for f in os.listdir(WATCH_FOLDER) if f.endswith(".torrent")])
    except:
        torrent_count = 0

    status_message = (
        f"╔═══════════════════════╗\n"
        f"      📊 *BOT STATUS*      \n"
        f"╚═══════════════════════╝\n\n"
        f"🟢 *System:* `ONLINE`\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"  🔑 *Your Access*\n"
        f"     {auth_icon} `{auth_text}`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"📁 *Watch Folder:*\n"
        f"   `{WATCH_FOLDER}`\n\n"
        f"📊 *Statistics:*\n"
        f"   • Authorized Users: `{len(ALLOWED_CHAT_IDS)}`\n"
        f"   • Torrents in Queue: `{torrent_count}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 Last checked: `Now`"
    )

    await update.message.reply_text(
        status_message, parse_mode="MarkdownV2", reply_markup=get_back_keyboard()
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu command."""
    chat_id = update.effective_chat.id
    menu_message = (
        "╔═══════════════════════╗\n"
        "       🎯 *MAIN MENU*       \n"
        "╚═══════════════════════╝\n\n"
        "Select an option below:\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    await update.message.reply_text(
        menu_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard(has_rss=bool(get_rss_url(chat_id)))
    )
