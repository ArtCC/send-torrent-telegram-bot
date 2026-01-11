#!/usr/bin/env python3
"""
Send Torrent Telegram Bot
Receives .torrent files and saves them to a shared folder for torrent clients.
"""

import os
import asyncio
import json
import math
import feedparser
from pathlib import Path
from typing import Dict, List, Optional
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

# Import configuration and models
from bot.config import (
    logger,
    TELEGRAM_BOT_TOKEN,
    ALLOWED_CHAT_IDS,
    WATCH_FOLDER,
    RSS_STORAGE_FILE,
    BATCH_TIMEOUT,
)
from bot.models import TorrentFile, batch_queues, batch_tasks
from bot.utils import escape_markdown_v2, is_authorized, get_main_menu_keyboard, get_back_keyboard
from bot.services import get_rss_url
from bot.handlers import (
    start_command,
    help_command,
    status_command,
    menu_command,
    setrss_command,
    browse_command,
    clearrss_command,
    handle_rss_browse,
    handle_rss_toggle,
    handle_rss_cancel,
    handle_rss_page_info,
    handle_rss_download,
)


# ==================== Document Handlers ====================

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
        
        # Build file list - same format as single file
        file_list = ""
        for idx, f in enumerate(successful, 1):
            escaped_name = escape_markdown_v2(f.name)
            file_list += f"{idx}\\. Name: `{escaped_name}`\n"
            file_list += f"   Size: `{f.size:.2f} KB`\n"
            file_list += f"   Status: `QUEUED`\n"
            if idx < len(successful):
                file_list += "\n"
        
        if failed:
            file_list += "\n\n*Failed Files:*\n"
            for idx, f in enumerate(failed, 1):
                escaped_name = escape_markdown_v2(f.name)
                file_list += f"{idx}\\. `{escaped_name}`\n"
        
        summary_message = (
            f"╔═══════════════════════╗\n"
            f"      ✅ *SUCCESS\\!*      \n"
            f"╚═══════════════════════╝\n\n"
            f"🎉 Multiple torrents received\\!\n\n"
            f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
            f"  📁 *Files Processed*\n\n"
            f"{file_list}"
            f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
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
            menu_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard(has_rss=bool(get_rss_url(chat_id)))
        )
    
    elif query.data == "rss_browse" or query.data.startswith("rss_page_"):
        await handle_rss_browse(update, context)
    
    elif query.data.startswith("rss_toggle_"):
        await handle_rss_toggle(update, context)
    
    elif query.data == "rss_cancel":
        await handle_rss_cancel(update, context)
    
    elif query.data == "rss_page_info":
        await handle_rss_page_info(update, context)
    
    elif query.data == "rss_download_selected":
        await handle_rss_download(update, context)

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

    elif query.data == "author":
        author_message = (
            "╔═══════════════════════╗\n"
            "      👨‍💻 *AUTHOR*      \n"
            "╚═══════════════════════╝\n\n"
            "*Arturo Carretero Calvo*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💻 *GitHub:*\n"
            "[github\\.com/ArtCC](https://github.com/ArtCC)\n\n"
            "🚀 Check out my other projects\\!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✨ *Built with:*\n"
            "GitHub Copilot \(Claude Sonnet 4\\.5\)\n\n"
            "📄 *License:* Apache 2\\.0"
        )
        await query.edit_message_text(
            author_message, parse_mode="MarkdownV2", reply_markup=get_back_keyboard()
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
    logger.info("Starting Send Torrent Telegram Bot...")

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
