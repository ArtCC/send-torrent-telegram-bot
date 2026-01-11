#!/usr/bin/env python3
"""
Telegram Torrent Bot
Receives .torrent files and saves them to a shared folder for torrent clients.
"""

import os
import asyncio
import json
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
from bot.services import load_rss_urls, save_rss_url, delete_rss_url, get_rss_url
from bot.handlers import start_command, help_command, status_command, menu_command


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
        
        # Get ALL entries (no limit)
        entries = feed.entries
        
        # Initialize selection set if not exists
        if 'rss_selected' not in context.user_data:
            context.user_data['rss_selected'] = set()
        
        selected = context.user_data['rss_selected']
        
        # Create buttons for each entry with visual indicators
        keyboard = []
        for idx, entry in enumerate(entries, 1):
            title = entry.get('title', 'Unknown')
            category = entry.get('category', '')
            
            # Add emoji based on category
            emoji = "📺" if "series" in category.lower() else "🎬" if "pel" in category.lower() else "📦"
            
            # Add checkbox indicator
            checkbox = "✅" if (idx-1) in selected else "☐"
            
            # Truncate title if too long (leave space for emoji and checkbox)
            max_length = 55
            if len(title) > max_length:
                title = title[:max_length-3] + "..."
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{checkbox} {emoji} {title}",
                    callback_data=f"rss_toggle_{idx-1}"
                )
            ])
        
        # Add action buttons
        action_buttons = []
        if selected:
            action_buttons.append(InlineKeyboardButton(
                f"⬇️ Download ({len(selected)})",
                callback_data="rss_download_selected"
            ))
        action_buttons.append(InlineKeyboardButton("🔙 Back", callback_data="menu"))
        keyboard.append(action_buttons)
        
        # Store feed entries in context for callback
        context.user_data['rss_entries'] = entries
        
        feed_title = feed.feed.get('title', 'RSS Feed')
        escaped_title = escape_markdown_v2(feed_title)
        
        total_text = f"{len(entries)} torrent" if len(entries) == 1 else f"{len(entries)} torrents"
        selected_text = f" \\| Selected: `{len(selected)}`" if selected else ""
        
        await loading_msg.edit_text(
            "╔═══════════════════════╗\n"
            "      📡 *RSS FEED*      \n"
            "╚═══════════════════════╝\n\n"
            f"🎯 *{escaped_title}*\n\n"
            f"📊 Total: `{total_text}`{selected_text}\n"
            f"🎬 Movies \\| 📺 Series \\| 📦 Others\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "☐ Click to select \\| ✅ Selected\n"
            "👇 Choose torrents to download:",
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
            menu_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard(has_rss=bool(get_rss_url(chat_id)))
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
        
        # Get ALL entries (no limit)
        entries = feed.entries
        
        # Initialize selection set if not exists
        if 'rss_selected' not in context.user_data:
            context.user_data['rss_selected'] = set()
        
        selected = context.user_data['rss_selected']
        
        # Create buttons for each entry with visual indicators
        keyboard = []
        for idx, entry in enumerate(entries, 1):
            title = entry.get('title', 'Unknown')
            category = entry.get('category', '')
            
            # Add emoji based on category
            emoji = "📺" if "series" in category.lower() else "🎬" if "pel" in category.lower() else "📦"
            
            # Add checkbox indicator
            checkbox = "✅" if (idx-1) in selected else "☐"
            
            # Truncate title if too long (leave space for emoji and checkbox)
            max_length = 55
            if len(title) > max_length:
                title = title[:max_length-3] + "..."
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{checkbox} {emoji} {title}",
                    callback_data=f"rss_toggle_{idx-1}"
                )
            ])
        
        # Add action buttons
        action_buttons = []
        if selected:
            action_buttons.append(InlineKeyboardButton(
                f"⬇️ Download ({len(selected)})",
                callback_data="rss_download_selected"
            ))
        action_buttons.append(InlineKeyboardButton("🔙 Back", callback_data="menu"))
        keyboard.append(action_buttons)
        
        # Store feed entries in context for callback
        context.user_data['rss_entries'] = entries
        
        feed_title = feed.feed.get('title', 'RSS Feed')
        escaped_title = escape_markdown_v2(feed_title)
        
        total_text = f"{len(entries)} torrent" if len(entries) == 1 else f"{len(entries)} torrents"
        selected_text = f" \\| Selected: `{len(selected)}`" if selected else ""
        
        await query.edit_message_text(
            "╔═══════════════════════╗\n"
            "      📡 *RSS FEED*      \n"
            "╚═══════════════════════╝\n\n"
            f"🎯 *{escaped_title}*\n\n"
            f"📊 Total: `{total_text}`{selected_text}\n"
            f"🎬 Movies \\| 📺 Series \\| 📦 Others\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "☐ Click to select \\| ✅ Selected\n"
            "👇 Choose torrents to download:",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith("rss_toggle_"):
        # Handle RSS torrent selection toggle
        try:
            idx = int(query.data.split("_")[2])
            
            # Toggle selection
            if 'rss_selected' not in context.user_data:
                context.user_data['rss_selected'] = set()
            
            selected = context.user_data['rss_selected']
            if idx in selected:
                selected.remove(idx)
                await query.answer("☐ Unselected")
            else:
                selected.add(idx)
                await query.answer("✅ Selected")
            
            # Refresh the list to show updated checkboxes
            entries = context.user_data.get('rss_entries', [])
            
            # Rebuild keyboard with updated selections
            keyboard = []
            for i, entry in enumerate(entries, 1):
                title = entry.get('title', 'Unknown')
                category = entry.get('category', '')
                
                emoji = "📺" if "series" in category.lower() else "🎬" if "pel" in category.lower() else "📦"
                checkbox = "✅" if (i-1) in selected else "☐"
                
                max_length = 55
                if len(title) > max_length:
                    title = title[:max_length-3] + "..."
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"{checkbox} {emoji} {title}",
                        callback_data=f"rss_toggle_{i-1}"
                    )
                ])
            
            # Add action buttons
            action_buttons = []
            if selected:
                action_buttons.append(InlineKeyboardButton(
                    f"⬇️ Download ({len(selected)})",
                    callback_data="rss_download_selected"
                ))
            action_buttons.append(InlineKeyboardButton("🔙 Back", callback_data="menu"))
            keyboard.append(action_buttons)
            
            # Update message
            feed = feedparser.parse(get_rss_url(chat_id))
            feed_title = feed.feed.get('title', 'RSS Feed')
            escaped_title = escape_markdown_v2(feed_title)
            
            total_text = f"{len(entries)} torrent" if len(entries) == 1 else f"{len(entries)} torrents"
            selected_text = f" \\| Selected: `{len(selected)}`" if selected else ""
            
            await query.edit_message_text(
                "╔═══════════════════════╗\n"
                "      📡 *RSS FEED*      \n"
                "╚═══════════════════════╝\n\n"
                f"🎯 *{escaped_title}*\n\n"
                f"📊 Total: `{total_text}`{selected_text}\n"
                f"🎬 Movies \\| 📺 Series \\| 📦 Others\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "☐ Click to select \\| ✅ Selected\n"
                "👇 Choose torrents to download:",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Error toggling RSS selection: {e}")
            await query.answer("❌ Error updating selection", show_alert=True)
    
    elif query.data == "rss_download_selected":
        # Handle downloading selected torrents
        try:
            selected = context.user_data.get('rss_selected', set())
            entries = context.user_data.get('rss_entries', [])
            
            if not selected:
                await query.answer("⚠️ No torrents selected!", show_alert=True)
                return
            
            await query.answer(f"⬇️ Downloading {len(selected)} torrent(s)...")
            
            import urllib.request
            import tempfile
            
            downloaded = []
            failed = []
            
            for idx in selected:
                if idx >= len(entries):
                    continue
                
                entry = entries[idx]
                torrent_url = entry.get('link', '')
                torrent_title = entry.get('title', 'Unknown')
                
                if not torrent_url:
                    failed.append(torrent_title)
                    continue
                
                try:
                    # Download torrent
                    with tempfile.NamedTemporaryFile(suffix='.torrent', delete=False) as temp_file:
                        temp_path = temp_file.name
                    
                    urllib.request.urlretrieve(torrent_url, temp_path)
                    
                    # Save to watch folder
                    file_name = f"{torrent_title[:100]}.torrent".replace('/', '_').replace('\\', '_')
                    file_path = os.path.join(WATCH_FOLDER, file_name)
                    
                    with open(temp_path, 'rb') as src:
                        with open(file_path, 'wb') as dst:
                            dst.write(src.read())
                    
                    file_size = os.path.getsize(file_path) / 1024  # KB
                    downloaded.append((file_name, file_size))
                    
                    logger.info(f"RSS torrent downloaded: {file_name} (from {user_name}, chat ID: {chat_id})")
                    
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                        
                except Exception as e:
                    logger.error(f"Error downloading {torrent_title}: {e}")
                    failed.append(torrent_title)
            
            # Clear selection
            context.user_data['rss_selected'] = set()
            
            # Build summary message
            file_list = ""
            for idx, (name, size) in enumerate(downloaded, 1):
                escaped_name = escape_markdown_v2(name)
                file_list += f"{idx}\\. Name: `{escaped_name}`\n"
                file_list += f"   Size: `{size:.2f} KB`\n"
                file_list += f"   Status: `QUEUED`\n"
                if idx < len(downloaded):
                    file_list += "\n"
            
            if failed:
                file_list += "\n\n*Failed:*\n"
                for idx, name in enumerate(failed, 1):
                    escaped_name = escape_markdown_v2(name)
                    file_list += f"{idx}\\. `{escaped_name}`\n"
            
            success_msg = "torrent" if len(downloaded) == 1 else "torrents"
            
            await query.edit_message_text(
                "╔═══════════════════════╗\n"
                "      ✅ *SUCCESS\\!*      \n"
                "╚═══════════════════════╝\n\n"
                f"🎉 {len(downloaded)} {success_msg} downloaded from RSS\\!\n\n"
                "┏━━━━━━━━━━━━━━━━━━━━┓\n"
                "  📁 *Downloaded Files*\n\n"
                f"{file_list}"
                "┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "🚀 Your torrent client will pick\n"
                "them up automatically\\!\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"💚 Happy downloading, *{user_name}*\\!",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error downloading selected torrents: {e}")
            await query.answer("❌ Error downloading torrents!", show_alert=True)

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
