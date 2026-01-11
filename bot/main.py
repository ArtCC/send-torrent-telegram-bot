#!/usr/bin/env python3
"""
Telegram Torrent Bot
Receives .torrent files and saves them to a shared folder for torrent clients.
"""

import os
import logging
import asyncio
import json
import feedparser
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Reduce httpx logging verbosity (suppress polling requests)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "").split(",")
WATCH_FOLDER = os.getenv("WATCH_FOLDER", "/watch")
RSS_STORAGE_FILE = os.getenv("RSS_STORAGE_FILE", "rss_urls.json")

# Batch processing configuration
BATCH_TIMEOUT = 2.0  # seconds to wait for more files
batch_queues: Dict[int, List["TorrentFile"]] = {}
batch_tasks: Dict[int, asyncio.Task] = {}


@dataclass
class TorrentFile:
    """Represents a torrent file to be processed."""
    name: str
    size: float  # in KB
    success: bool
    error: str = ""

# Validate configuration
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

if not ALLOWED_CHAT_IDS or ALLOWED_CHAT_IDS == [""]:
    raise ValueError("ALLOWED_CHAT_IDS environment variable is required")

# Convert chat IDs to integers and filter empty strings
ALLOWED_CHAT_IDS = [int(chat_id.strip()) for chat_id in ALLOWED_CHAT_IDS if chat_id.strip()]

# Ensure watch folder exists
Path(WATCH_FOLDER).mkdir(parents=True, exist_ok=True)

logger.info(f"Bot configured with {len(ALLOWED_CHAT_IDS)} allowed chat ID(s)")
logger.info(f"Watch folder: {WATCH_FOLDER}")


# ==================== RSS Storage Functions ====================

def load_rss_urls() -> Dict[int, str]:
    """Load RSS URLs from JSON file."""
    try:
        if os.path.exists(RSS_STORAGE_FILE):
            with open(RSS_STORAGE_FILE, 'r') as f:
                data = json.load(f)
                # Convert string keys back to integers
                return {int(k): v for k, v in data.items()}
        return {}
    except Exception as e:
        logger.error(f"Error loading RSS URLs: {e}")
        return {}


def save_rss_url(chat_id: int, rss_url: str) -> None:
    """Save RSS URL for a chat ID."""
    try:
        urls = load_rss_urls()
        urls[chat_id] = rss_url
        # Convert integer keys to strings for JSON
        with open(RSS_STORAGE_FILE, 'w') as f:
            json.dump({str(k): v for k, v in urls.items()}, f, indent=2)
        logger.info(f"RSS URL saved for chat ID {chat_id}")
    except Exception as e:
        logger.error(f"Error saving RSS URL: {e}")
        raise


def delete_rss_url(chat_id: int) -> bool:
    """Delete RSS URL for a chat ID. Returns True if deleted, False if not found."""
    try:
        urls = load_rss_urls()
        if chat_id in urls:
            del urls[chat_id]
            with open(RSS_STORAGE_FILE, 'w') as f:
                json.dump({str(k): v for k, v in urls.items()}, f, indent=2)
            logger.info(f"RSS URL deleted for chat ID {chat_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting RSS URL: {e}")
        return False


def get_rss_url(chat_id: int) -> Optional[str]:
    """Get RSS URL for a chat ID."""
    urls = load_rss_urls()
    return urls.get(chat_id)


# ==================== Authorization & Menu ====================

def escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def is_authorized(chat_id: int) -> bool:
    """Check if the chat ID is authorized to use the bot."""
    return chat_id in ALLOWED_CHAT_IDS


def get_main_menu_keyboard(chat_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Create the main menu keyboard with inline buttons."""
    keyboard = [
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
            InlineKeyboardButton("📊 Status", callback_data="status"),
        ],
        [
            InlineKeyboardButton("📋 How to Use", callback_data="howto"),
            InlineKeyboardButton("🔑 My Chat ID", callback_data="chatid"),
        ],
    ]
    
    # Add RSS button if user has RSS configured
    if chat_id and get_rss_url(chat_id):
        keyboard.append([
            InlineKeyboardButton("📡 Browse RSS Feed", callback_data="rss_browse")
        ])
    
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard with a back button."""
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
    return InlineKeyboardMarkup(keyboard)


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
        welcome_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard(chat_id)
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


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document/file messages."""
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name or "User"

    # Check authorization
    if not is_authorized(chat_id):
        logger.warning(f"Unauthorized access attempt from chat ID: {chat_id}")
        await update.message.reply_text(
            "╔═══════════════════════╗\n"
            "      🚫 *ACCESS DENIED*     \n"
            "╚═══════════════════════╝\n\n"
            "⛔ You are not authorized to use\n"
            "this bot\\.\n\n"
            "🔑 *Your Chat ID:* `{}`\n\n"
            "💡 Add this ID to `ALLOWED_CHAT_IDS`\n"
            "to gain access\\.\n\n"
            "Use /start for more info\\.".format(chat_id),
            parse_mode="MarkdownV2",
        )
        return

    document = update.message.document
    file_name = document.file_name
    file_size = document.file_size / 1024  # KB

    # Check if file is a torrent
    if not file_name.lower().endswith(".torrent"):
        keyboard = [[InlineKeyboardButton("📖 See Help", callback_data="help")]]
        await update.message.reply_text(
            "╔═══════════════════════╗\n"
            "     ⚠️ *INVALID FILE*     \n"
            "╚═══════════════════════╝\n\n"
            "❌ This is not a torrent file\\!\n\n"
            "📦 Please send only files with\n"
            "`.torrent` extension\\.\n\n"
            "💡 Drag \\& drop your torrent file\n"
            "or click the attachment button\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # Process the torrent file
    try:
        file = await context.bot.get_file(document.file_id)
        file_path = os.path.join(WATCH_FOLDER, file_name)
        await file.download_to_drive(file_path)
        
        logger.info(f"Torrent file saved: {file_name} (from {user_name}, chat ID: {chat_id})")
        
        torrent_file = TorrentFile(name=file_name, size=file_size, success=True)
        
    except Exception as e:
        logger.error(f"Error saving torrent file: {e}")
        torrent_file = TorrentFile(name=file_name, size=file_size, success=False, error=str(e))
    
    # Add to batch queue
    if chat_id not in batch_queues:
        batch_queues[chat_id] = []
    batch_queues[chat_id].append(torrent_file)
    
    # Cancel existing batch task if any
    if chat_id in batch_tasks:
        batch_tasks[chat_id].cancel()
    
    # Create new batch task
    batch_tasks[chat_id] = asyncio.create_task(
        send_batch_summary(update, context, chat_id, user_name)
    )


async def send_batch_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_name: str) -> None:
    """Send summary of batched torrent files after timeout."""
    try:
        await asyncio.sleep(BATCH_TIMEOUT)
        
        # Get all files from queue
        files = batch_queues.get(chat_id, [])
        if not files:
            return
        
        # Clear queue
        batch_queues[chat_id] = []
        if chat_id in batch_tasks:
            del batch_tasks[chat_id]
        
        # Count successes and failures
        successful = [f for f in files if f.success]
        failed = [f for f in files if not f.success]
        
        # If only one file, use original format
        if len(files) == 1:
            file = files[0]
            if file.success:
                escaped_name = escape_markdown_v2(file.name)
                success_message = (
                    f"╔═══════════════════════╗\n"
                    f"      ✅ *SUCCESS\\!*      \n"
                    f"╚═══════════════════════╝\n\n"
                    f"🎉 Torrent received and saved\\!\n\n"
                    f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
                    f"  📁 *File Details*\n"
                    f"  • Name: `{escaped_name}`\n"
                    f"  • Size: `{file.size:.2f} KB`\n"
                    f"  • Status: `QUEUED`\n"
                    f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
                    f"🚀 Your torrent client will pick\n"
                    f"it up automatically\\!\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💚 Happy downloading, *{user_name}*\\!"
                )
                keyboard = [
                    [
                        InlineKeyboardButton("📊 Check Status", callback_data="status"),
                        InlineKeyboardButton("🔙 Menu", callback_data="menu"),
                    ]
                ]
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=success_message,
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                keyboard = [[InlineKeyboardButton("🔄 Try Again", callback_data="menu")]]
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "╔═══════════════════════╗\n"
                        "        ❌ *ERROR*        \n"
                        "╚═══════════════════════╝\n\n"
                        "⚠️ Failed to save the torrent\n"
                        "file\\. Please try again\\.\n\n"
                        "🔧 If the problem persists,\n"
                        "contact the administrator\\."
                    ),
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            return
        
        # Multiple files - create batch summary
        total_size = sum(f.size for f in successful)
        
        # Build file list
        file_list = ""
        for f in successful:
            escaped_name = escape_markdown_v2(f.name)
            file_list += f"  • `{escaped_name}` \\({f.size:.2f} KB\\)\n"
        
        if failed:
            file_list += "\n*Failed:*\n"
            for f in failed:
                escaped_name = escape_markdown_v2(f.name)
                file_list += f"  • `{escaped_name}` ❌\n"
        
        summary_message = (
            f"╔═══════════════════════╗\n"
            f"      ✅ *SUCCESS\\!*      \n"
            f"╚═══════════════════════╝\n\n"
            f"🎉 Multiple torrents received\\!\n\n"
            f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
            f"  📁 *Files Processed*\n"
            f"  • Total: `{len(files)}`\n"
            f"  • Success: `{len(successful)}`\n"
            f"  • Failed: `{len(failed)}`\n"
            f"  • Total Size: `{total_size:.2f} KB`\n"
            f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"*Files:*\n{file_list}\n"
            f"🚀 Your torrent client will pick\n"
            f"them up automatically\\!\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💚 Happy downloading, *{user_name}*\\!"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Check Status", callback_data="status"),
                InlineKeyboardButton("🔙 Menu", callback_data="menu"),
            ]
        ]
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=summary_message,
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except asyncio.CancelledError:
        # Task was cancelled, do nothing
        pass
    except Exception as e:
        logger.error(f"Error sending batch summary: {e}")


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
        menu_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard(chat_id)
    )


# ==================== RSS Commands ====================

async def setrss_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /setrss command to set RSS feed URL."""
    chat_id = update.effective_chat.id
    
    if not is_authorized(chat_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\\.",
            parse_mode="MarkdownV2"
        )
        return
    
    # Check if URL was provided
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "╔═══════════════════════╗\n"
            "      📡 *SET RSS FEED*      \n"
            "╚═══════════════════════╝\n\n"
            "⚠️ Please provide an RSS URL\\!\n\n"
            "*Usage:*\n"
            "`/setrss <RSS\\_URL>`\n\n"
            "*Example:*\n"
            "`/setrss https://example\\.com/rss/feed`\n\n"
            "💡 Your personal RSS URL from\n"
            "your tracker\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    rss_url = " ".join(context.args)
    
    # Basic URL validation
    if not rss_url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ Invalid URL\\! Please provide\n"
            "a valid HTTP or HTTPS URL\\.",
            parse_mode="MarkdownV2"
        )
        return
    
    try:
        save_rss_url(chat_id, rss_url)
        
        # Escape URL for MarkdownV2
        escaped_url = rss_url.replace('.', '\\.').replace('-', '\\-').replace('_', '\\_')
        
        await update.message.reply_text(
            "╔═══════════════════════╗\n"
            "      ✅ *RSS SAVED\\!*      \n"
            "╚═══════════════════════╝\n\n"
            "🎉 Your RSS feed URL has been\n"
            "saved successfully\\!\n\n"
            "📡 *Feed URL:*\n"
            f"`{escaped_url}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 Use `/browse` to view your feed\\!\n\n"
            "🔧 Use `/clearrss` to remove it\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    except Exception as e:
        logger.error(f"Error saving RSS URL: {e}")
        await update.message.reply_text(
            "❌ Error saving RSS URL\\."
            "Please try again\\.",
            parse_mode="MarkdownV2"
        )


async def browse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /browse command to view RSS feed."""
    chat_id = update.effective_chat.id
    
    if not is_authorized(chat_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\\.",
            parse_mode="MarkdownV2"
        )
        return
    
    rss_url = get_rss_url(chat_id)
    
    if not rss_url:
        await update.message.reply_text(
            "╔═══════════════════════╗\n"
            "      📡 *NO RSS FEED*      \n"
            "╚═══════════════════════╝\n\n"
            "⚠️ You haven't configured an\n"
            "RSS feed yet\\!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 Use `/setrss <URL>` to set\n"
            "your RSS feed URL first\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Send loading message
    loading_msg = await update.message.reply_text(
        "📡 Loading RSS feed\\.\\.\\.\\.\\n"
        "Please wait\\.",
        parse_mode="MarkdownV2"
    )
    
    try:
        # Parse RSS feed
        feed = feedparser.parse(rss_url)
        
        if feed.bozo and not feed.entries:
            await loading_msg.edit_text(
                "❌ Failed to parse RSS feed\\!\n\n"
                "Please check your RSS URL\\.",
                parse_mode="MarkdownV2"
            )
            return
        
        if not feed.entries:
            await loading_msg.edit_text(
                "📡 *RSS Feed Empty*\n\n"
                "No torrents found in the feed\\.",
                parse_mode="MarkdownV2"
            )
            return
        
        # Get last 15 entries
        entries = feed.entries[:15]
        
        # Create buttons for each entry
        keyboard = []
        for idx, entry in enumerate(entries, 1):
            title = entry.get('title', 'Unknown')
            # Truncate title if too long
            if len(title) > 50:
                title = title[:47] + "..."
            
            # Store the link in callback_data with a prefix
            # We'll use the entry's link for downloading
            keyboard.append([
                InlineKeyboardButton(
                    f"{idx}. {title}",
                    callback_data=f"rss_dl_{idx-1}"  # Index in the list
                )
            ])
        
        # Add back button
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")])
        
        # Store feed entries in context for callback
        context.user_data['rss_entries'] = entries
        
        feed_title = feed.feed.get('title', 'RSS Feed')
        escaped_title = feed_title.replace('_', '\\_').replace('.', '\\.').replace('-', '\\-')
        
        await loading_msg.edit_text(
            "╔═══════════════════════╗\n"
            "      📡 *RSS FEED*      \n"
            "╚═══════════════════════╝\n\n"
            f"*{escaped_title}*\n\n"
            f"📊 Showing {len(entries)} latest torrents\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "👇 Click a torrent to download:",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error fetching RSS feed: {e}")
        await loading_msg.edit_text(
            "❌ Error loading RSS feed\\!\n\n"
            "Please check your connection\n"
            "or RSS URL\\.",
            parse_mode="MarkdownV2"
        )


async def clearrss_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clearrss command to remove RSS feed URL."""
    chat_id = update.effective_chat.id
    
    if not is_authorized(chat_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\\.",
            parse_mode="MarkdownV2"
        )
        return
    
    if delete_rss_url(chat_id):
        await update.message.reply_text(
            "╔═══════════════════════╗\n"
            "      ✅ *RSS CLEARED\\!*      \n"
            "╚═══════════════════════╝\n\n"
            "🗑️ Your RSS feed URL has been\n"
            "removed successfully\\!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 Use `/setrss <URL>` to set\n"
            "a new RSS feed\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    else:
        await update.message.reply_text(
            "⚠️ No RSS feed configured\\!\n\n"
            "Use `/setrss <URL>` to set one\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )


# ==================== Button Callbacks ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()

    chat_id = query.from_user.id
    user_name = query.from_user.first_name or "User"

    if query.data == "menu":
        menu_message = (
            "╔═══════════════════════╗\n"
            "       🎯 *MAIN MENU*       \n"
            "╚═══════════════════════╝\n\n"
            "Select an option below:\n\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            menu_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard(chat_id)
        )
    
    elif query.data == "rss_browse":
        # Handle RSS browse button from menu
        rss_url = get_rss_url(chat_id)
        
        if not rss_url:
            await query.edit_message_text(
                "╔═══════════════════════╗\n"
                "      📡 *NO RSS FEED*      \n"
                "╚═══════════════════════╝\n\n"
                "⚠️ You haven't configured an\n"
                "RSS feed yet\\!\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "💡 Use `/setrss <URL>` to set\n"
                "your RSS feed URL first\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard()
            )
            return
        
        # Show loading
        await query.edit_message_text(
            "📡 Loading RSS feed\\.\\.\\.\\.\\n"
            "Please wait\\.",
            parse_mode="MarkdownV2"
        )
        
        try:
            # Parse RSS feed
            feed = feedparser.parse(rss_url)
            
            if feed.bozo and not feed.entries:
                await query.edit_message_text(
                    "❌ Failed to parse RSS feed\\!\n\n"
                    "Please check your RSS URL\\.",
                    parse_mode="MarkdownV2",
                    reply_markup=get_back_keyboard()
                )
                return
            
            if not feed.entries:
                await query.edit_message_text(
                    "📡 *RSS Feed Empty*\n\n"
                    "No torrents found in the feed\\.",
                    parse_mode="MarkdownV2",
                    reply_markup=get_back_keyboard()
                )
                return
            
            # Get last 15 entries
            entries = feed.entries[:15]
            
            # Create buttons for each entry
            keyboard = []
            for idx, entry in enumerate(entries, 1):
                title = entry.get('title', 'Unknown')
                # Truncate title if too long
                if len(title) > 50:
                    title = title[:47] + "..."
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"{idx}. {title}",
                        callback_data=f"rss_dl_{idx-1}"
                    )
                ])
            
            # Add back button
            keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")])
            
            # Store feed entries in context for callback
            context.user_data['rss_entries'] = entries
            
            feed_title = feed.feed.get('title', 'RSS Feed')
            escaped_title = feed_title.replace('_', '\\_').replace('.', '\\.').replace('-', '\\-')
            
            await query.edit_message_text(
                "╔═══════════════════════╗\n"
                "      📡 *RSS FEED*      \n"
                "╚═══════════════════════╝\n\n"
                f"*{escaped_title}*\n\n"
                f"📊 Showing {len(entries)} latest torrents\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "👇 Click a torrent to download:",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Error fetching RSS feed: {e}")
            await query.edit_message_text(
                "❌ Error loading RSS feed\\!\n\n"
                "Please check your connection\n"
                "or RSS URL\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard()
            )
    
    elif query.data.startswith("rss_dl_"):
        # Handle RSS torrent download
        try:
            idx = int(query.data.split("_")[2])
            entries = context.user_data.get('rss_entries', [])
            
            if idx >= len(entries):
                await query.answer("❌ Torrent not found!", show_alert=True)
                return
            
            entry = entries[idx]
            torrent_url = entry.get('link', '')
            torrent_title = entry.get('title', 'Unknown')
            
            if not torrent_url:
                await query.answer("❌ Invalid torrent link!", show_alert=True)
                return
            
            # Show loading
            await query.answer("⬇️ Downloading torrent...")
            
            # Download the torrent file from RSS
            import urllib.request
            import tempfile
            
            # Create temp file
            with tempfile.NamedTemporaryFile(suffix='.torrent', delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Download torrent
                urllib.request.urlretrieve(torrent_url, temp_path)
                
                # Read file and save to watch folder
                file_name = f"{torrent_title[:100]}.torrent".replace('/', '_').replace('\\', '_')
                file_path = os.path.join(WATCH_FOLDER, file_name)
                
                # Copy to watch folder
                with open(temp_path, 'rb') as src:
                    with open(file_path, 'wb') as dst:
                        dst.write(src.read())
                
                # Get file size
                file_size = os.path.getsize(file_path) / 1024  # KB
                
                logger.info(f"RSS torrent downloaded: {file_name} (from {user_name}, chat ID: {chat_id})")
                
                # Escape title for MarkdownV2
                escaped_title = torrent_title.replace('_', '\\_').replace('.', '\\.').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('-', '\\-').replace('!', '\\!')
                
                await query.edit_message_text(
                    "╔═══════════════════════╗\n"
                    "      ✅ *SUCCESS\\!*      \n"
                    "╚═══════════════════════╝\n\n"
                    "🎉 Torrent downloaded from RSS\\!\n\n"
                    "┏━━━━━━━━━━━━━━━━━━━━┓\n"
                    "  📁 *Torrent Details*\n"
                    f"  • Name: `{file_name}`\n"
                    f"  • Size: `{file_size:.2f} KB`\n"
                    "  • Status: `QUEUED`\n"
                    "┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
                    "🚀 Your torrent client will pick\n"
                    "it up automatically\\!\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"💚 Happy downloading, *{user_name}*\\!",
                    parse_mode="MarkdownV2",
                    reply_markup=get_back_keyboard()
                )
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Error downloading RSS torrent: {e}")
            await query.answer("❌ Error downloading torrent!", show_alert=True)

    elif query.data == "help":
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
        await query.edit_message_text(
            help_message, parse_mode="MarkdownV2", reply_markup=get_back_keyboard()
        )

    elif query.data == "status":
        is_auth = is_authorized(chat_id)
        auth_icon = "✅" if is_auth else "❌"
        auth_text = "AUTHORIZED" if is_auth else "NOT AUTHORIZED"

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
        await query.edit_message_text(
            status_message, parse_mode="MarkdownV2", reply_markup=get_back_keyboard()
        )

    elif query.data == "howto":
        howto_message = (
            "╔═══════════════════════╗\n"
            "      📋 *HOW TO USE*      \n"
            "╚═══════════════════════╝\n\n"
            "*Step\\-by\\-step Guide:*\n\n"
            "1️⃣ Find a `.torrent` file\n"
            "2️⃣ Send it to this bot\n"
            "3️⃣ Wait for confirmation\n"
            "4️⃣ Check your torrent client\n"
            "5️⃣ Start downloading\\!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✨ *Pro Tips:*\n\n"
            "• Only `.torrent` files accepted\n"
            "• Files saved instantly\n"
            "• Auto\\-detected by client\n"
            "• Check status anytime\n\n"
            "🎯 It's that simple\\!"
        )
        await query.edit_message_text(
            howto_message, parse_mode="MarkdownV2", reply_markup=get_back_keyboard()
        )

    elif query.data == "chatid":
        chat_id_message = (
            f"╔═══════════════════════╗\n"
            f"      🔑 *YOUR CHAT ID*      \n"
            f"╚═══════════════════════╝\n\n"
            f"👤 *User:* {user_name}\n"
            f"🆔 *Chat ID:* `{chat_id}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💡 *Usage:*\n\n"
            f"Add this ID to the\n"
            f"`ALLOWED_CHAT_IDS` variable\n"
            f"in your `.env` file\\.\n\n"
            f"Example:\n"
            f"`ALLOWED_CHAT_IDS={chat_id}`\n\n"
            f"⚠️ Keep this ID private\\!"
        )
        await query.edit_message_text(
            chat_id_message, parse_mode="MarkdownV2", reply_markup=get_back_keyboard()
        )


async def handle_other_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle other types of messages."""
    chat_id = update.effective_chat.id

    if not is_authorized(chat_id):
        return

    keyboard = [
        [
            InlineKeyboardButton("📖 Help", callback_data="help"),
            InlineKeyboardButton("📋 How to Use", callback_data="howto"),
        ]
    ]

    await update.message.reply_text(
        "╔═══════════════════════╗\n"
        "       ℹ️ *INFO*       \n"
        "╚═══════════════════════╝\n\n"
        "📦 Please send me a `.torrent` file\\.\n\n"
        "Use the buttons below for help\\!",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def setup_bot_commands(application: Application) -> None:
    """Set up bot commands for the menu."""
    commands = [
        BotCommand("start", "🏠 Start the bot and show main menu"),
        BotCommand("menu", "🎯 Show interactive menu"),
        BotCommand("help", "📖 Show help and usage guide"),
        BotCommand("status", "📊 Check bot status and info"),
        BotCommand("setrss", "📡 Set your RSS feed URL"),
        BotCommand("browse", "🔎 Browse your RSS feed"),
        BotCommand("clearrss", "🗑️ Remove your RSS feed"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    """Start the bot."""
    logger.info("Starting Telegram Torrent Bot...")

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Set up bot commands
    application.post_init = setup_bot_commands

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("setrss", setrss_command))
    application.add_handler(CommandHandler("browse", browse_command))
    application.add_handler(CommandHandler("clearrss", clearrss_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_other_messages))

    # Start the bot
    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
