"""
RSS Handlers
Command and callback handlers for RSS feed functionality.
"""

import os
import math
import urllib.request
import tempfile
import feedparser
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from bot.config import logger, WATCH_FOLDER
from bot.utils import escape_markdown_v2, is_authorized, get_main_menu_keyboard, get_back_keyboard
from bot.services import save_rss_url, delete_rss_url, get_rss_url, get_all_rss, has_rss, MAX_RSS_FEEDS


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
    
    # Check if URL and name were provided
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📡 *SET RSS FEED*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ Please provide URL and name\\!\n\n"
            "*Usage:*\n"
            "`/setrss <URL> <name>`\n\n"
            "*Example:*\n"
            "`/setrss https://example\\.com/rss MyTracker`\n\n"
            "💡 Name cannot contain spaces\\.\n"
            f"📊 Maximum {MAX_RSS_FEEDS} RSS feeds allowed\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    rss_url = context.args[0]
    rss_name = context.args[1]
    
    # Basic URL validation
    if not rss_url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ Invalid URL\\! Please provide\n"
            "a valid HTTP or HTTPS URL\\.",
            parse_mode="MarkdownV2"
        )
        return
    
    # Save RSS
    success, message = save_rss_url(chat_id, rss_name, rss_url)
    
    if success:
        escaped_name = escape_markdown_v2(rss_name)
        escaped_url_display = rss_url[:50] + "..." if len(rss_url) > 50 else rss_url
        escaped_url_display = escape_markdown_v2(escaped_url_display)
        
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ *RSS SAVED\\!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎉 RSS feed saved successfully\\!\n\n"
            f"📛 *Name:* `{escaped_name}`\n"
            f"🔗 *URL:* `{escaped_url_display}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 Use `/browse` to view your feeds\\!\n"
            "🗑️ Use `/clearrss` to manage them\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    else:
        escaped_message = escape_markdown_v2(message)
        await update.message.reply_text(
            f"❌ {escaped_message}\n\n"
            f"📊 Limit: {MAX_RSS_FEEDS} feeds per user\\.",
            parse_mode="MarkdownV2"
        )


async def browse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /browse command to view RSS feeds."""
    chat_id = update.effective_chat.id
    
    if not is_authorized(chat_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\\.",
            parse_mode="MarkdownV2"
        )
        return
    
    feeds = get_all_rss(chat_id)
    
    if not feeds:
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📡 *NO RSS FEEDS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ You haven't configured any\n"
            "RSS feeds yet\\!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 Use `/setrss <URL> <name>`\n"
            "to add your first RSS feed\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Create buttons for each RSS feed
    keyboard = []
    for name in feeds.keys():
        keyboard.append([
            InlineKeyboardButton(f"📡 {name}", callback_data=f"rss_select_{name}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu")])
    
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📡 *YOUR RSS FEEDS*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 You have `{len(feeds)}/{MAX_RSS_FEEDS}` feeds\\.\n\n"
        "👇 Select a feed to browse:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
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
    
    feeds = get_all_rss(chat_id)
    
    if not feeds:
        await update.message.reply_text(
            "⚠️ No RSS feeds configured\\!\n\n"
            "Use `/setrss <URL> <name>` to add one\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Create buttons for each RSS feed
    keyboard = []
    for name in feeds.keys():
        keyboard.append([
            InlineKeyboardButton(f"🗑️ {name}", callback_data=f"rss_delete_{name}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu")])
    
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🗑️ *DELETE RSS FEED*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ Select a feed to delete:\n\n"
        "👇 Choose carefully:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==================== RSS Callbacks ====================

async def handle_rss_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle RSS feed selection from browse menu."""
    query = update.callback_query
    chat_id = query.from_user.id
    
    # Extract feed name from callback data
    feed_name = query.data.replace("rss_select_", "")
    
    feeds = get_all_rss(chat_id)
    rss_url = feeds.get(feed_name)
    
    if not rss_url:
        await query.answer("❌ Feed not found!", show_alert=True)
        return
    
    # Store current feed name in context
    context.user_data['rss_current_feed'] = feed_name
    context.user_data['rss_current_page'] = 0
    context.user_data['rss_selected'] = set()
    
    # Show loading
    await query.edit_message_text(
        f"📡 Loading *{escape_markdown_v2(feed_name)}*\\.\\.\\.\n"
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
    
    # Store feed entries in context
    context.user_data['rss_entries'] = feed.entries
    context.user_data['rss_feed_title'] = feed.feed.get('title', feed_name)
    
    # Display first page
    await _display_rss_page(query, context, 0)


async def handle_rss_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle RSS feed deletion request - show confirmation."""
    query = update.callback_query
    chat_id = query.from_user.id
    
    # Extract feed name from callback data
    feed_name = query.data.replace("rss_delete_", "")
    
    # Store name for confirmation
    context.user_data['rss_delete_pending'] = feed_name
    
    escaped_name = escape_markdown_v2(feed_name)
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, delete", callback_data=f"rss_confirm_delete_{feed_name}"),
            InlineKeyboardButton("❌ No, cancel", callback_data="rss_cancel_delete")
        ]
    ]
    
    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *CONFIRM DELETE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Are you sure you want to delete\n"
        f"the RSS feed `{escaped_name}`\\?\n\n"
        "⚠️ This action cannot be undone\\!",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_rss_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmed RSS feed deletion."""
    query = update.callback_query
    chat_id = query.from_user.id
    
    # Extract feed name
    feed_name = query.data.replace("rss_confirm_delete_", "")
    
    if delete_rss_url(chat_id, feed_name):
        escaped_name = escape_markdown_v2(feed_name)
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ *RSS DELETED\\!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🗑️ Feed `{escaped_name}` has been\n"
            "removed successfully\\!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 Use `/setrss <URL> <name>`\n"
            "to add a new feed\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    else:
        await query.answer("❌ Error deleting feed!", show_alert=True)
    
    # Clear pending delete
    context.user_data.pop('rss_delete_pending', None)


async def handle_rss_cancel_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancelled RSS feed deletion."""
    query = update.callback_query
    chat_id = query.from_user.id
    
    context.user_data.pop('rss_delete_pending', None)
    
    # Return to clearrss menu
    feeds = get_all_rss(chat_id)
    
    if not feeds:
        await query.edit_message_text(
            "✅ Operation cancelled\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    keyboard = []
    for name in feeds.keys():
        keyboard.append([
            InlineKeyboardButton(f"🗑️ {name}", callback_data=f"rss_delete_{name}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu")])
    
    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🗑️ *DELETE RSS FEED*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ Select a feed to delete:\n\n"
        "👇 Choose carefully:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_rss_browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle RSS browse button from main menu."""
    query = update.callback_query
    chat_id = query.from_user.id
    
    feeds = get_all_rss(chat_id)
    
    if not feeds:
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📡 *NO RSS FEEDS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ You haven't configured any\n"
            "RSS feeds yet\\!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 Use `/setrss <URL> <name>`\n"
            "to add your first RSS feed\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # If only one feed, go directly to it
    if len(feeds) == 1:
        feed_name = list(feeds.keys())[0]
        context.user_data['rss_current_feed'] = feed_name
        context.user_data['rss_current_page'] = 0
        context.user_data['rss_selected'] = set()
        
        rss_url = feeds[feed_name]
        
        await query.edit_message_text(
            f"📡 Loading *{escape_markdown_v2(feed_name)}*\\.\\.\\.\n"
            "Please wait\\.",
            parse_mode="MarkdownV2"
        )
        
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
        
        context.user_data['rss_entries'] = feed.entries
        context.user_data['rss_feed_title'] = feed.feed.get('title', feed_name)
        
        await _display_rss_page(query, context, 0)
        return
    
    # Multiple feeds - show selection
    keyboard = []
    for name in feeds.keys():
        keyboard.append([
            InlineKeyboardButton(f"📡 {name}", callback_data=f"rss_select_{name}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu")])
    
    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📡 *YOUR RSS FEEDS*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 You have `{len(feeds)}/{MAX_RSS_FEEDS}` feeds\\.\n\n"
        "👇 Select a feed to browse:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_rss_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle RSS pagination."""
    query = update.callback_query
    
    try:
        page = int(query.data.split("_")[2])
        context.user_data['rss_current_page'] = page
        await _display_rss_page(query, context, page)
    except (ValueError, IndexError):
        await query.answer("❌ Error navigating pages", show_alert=True)


async def _display_rss_page(query, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Display RSS feed page with pagination."""
    entries = context.user_data.get('rss_entries', [])
    feed_title = context.user_data.get('rss_feed_title', 'RSS Feed')
    feed_name = context.user_data.get('rss_current_feed', '')
    selected = context.user_data.get('rss_selected', set())
    
    # Pagination
    items_per_page = 15
    total_pages = math.ceil(len(entries) / items_per_page) if entries else 1
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(entries))
    page_entries = entries[start_idx:end_idx]
    
    # Create buttons for current page entries
    keyboard = []
    for i, entry in enumerate(page_entries):
        global_idx = start_idx + i
        title = entry.get('title', 'Unknown')
        category = entry.get('category', '')
        
        emoji = "📺" if "series" in category.lower() else "🎬" if "pel" in category.lower() else "📦"
        checkbox = "✅" if global_idx in selected else "☐"
        
        max_length = 55
        if len(title) > max_length:
            title = title[:max_length-3] + "..."
        
        keyboard.append([
            InlineKeyboardButton(
                f"{checkbox} {emoji} {title}",
                callback_data=f"rss_toggle_{global_idx}"
            )
        ])
    
    # Add download button if selections
    if selected:
        keyboard.append([
            InlineKeyboardButton(
                f"⬇️ Download ({len(selected)})",
                callback_data="rss_download_selected"
            )
        ])
    
    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"rss_page_{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="rss_page_info"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"rss_page_{page+1}"))
    
    keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="rss_cancel")])
    
    escaped_title = escape_markdown_v2(feed_title)
    escaped_feed_name = escape_markdown_v2(feed_name)
    total_text = f"{len(entries)} torrent" if len(entries) == 1 else f"{len(entries)} torrents"
    selected_text = f" \\| Selected: `{len(selected)}`" if selected else ""
    page_info = f"Page {page+1}/{total_pages} \\({start_idx+1}\\-{end_idx}\\)"
    
    try:
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 *{escaped_feed_name}*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 *{escaped_title}*\n\n"
            f"📊 Total: `{total_text}`{selected_text}\n"
            f"📄 {page_info}\n"
            f"🎬 Movies \\| 📺 Series \\| 📦 Others\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "☐ Click to select \\| ✅ Selected\n"
            "👇 Choose torrents to download:",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise


async def handle_rss_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle RSS torrent selection toggle."""
    query = update.callback_query
    
    try:
        idx = int(query.data.split("_")[2])
        
        if 'rss_selected' not in context.user_data:
            context.user_data['rss_selected'] = set()
        
        selected = context.user_data['rss_selected']
        if idx in selected:
            selected.remove(idx)
            await query.answer("☐ Unselected")
        else:
            selected.add(idx)
            await query.answer("✅ Selected")
        
        page = context.user_data.get('rss_current_page', 0)
        await _display_rss_page(query, context, page)
        
    except Exception as e:
        logger.error(f"Error toggling RSS selection: {e}")
        await query.answer("❌ Error updating selection", show_alert=True)


async def handle_rss_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancel button - clear RSS context and return to menu."""
    query = update.callback_query
    chat_id = query.from_user.id
    
    context.user_data.pop('rss_selected', None)
    context.user_data.pop('rss_entries', None)
    context.user_data.pop('rss_current_page', None)
    context.user_data.pop('rss_feed_title', None)
    context.user_data.pop('rss_current_feed', None)
    
    menu_message = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 *MAIN MENU*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Select an option below:"
    )
    await query.edit_message_text(
        menu_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard(has_rss=has_rss(chat_id))
    )


async def handle_rss_page_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle page info button click."""
    query = update.callback_query
    page = context.user_data.get('rss_current_page', 0)
    entries = context.user_data.get('rss_entries', [])
    items_per_page = 15
    total_pages = math.ceil(len(entries) / items_per_page) if entries else 1
    await query.answer(f"📄 Page {page+1} of {total_pages}", show_alert=False)


async def handle_rss_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle downloading selected torrents."""
    query = update.callback_query
    chat_id = query.from_user.id
    user_name = query.from_user.first_name or "User"
    
    try:
        selected = context.user_data.get('rss_selected', set())
        entries = context.user_data.get('rss_entries', [])
        
        if not selected:
            await query.answer("⚠️ No torrents selected!", show_alert=True)
            return
        
        await query.answer(f"⬇️ Downloading {len(selected)} torrent(s)...")
        
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
                with tempfile.NamedTemporaryFile(suffix='.torrent', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                urllib.request.urlretrieve(torrent_url, temp_path)
                
                file_name = f"{torrent_title[:100]}.torrent".replace('/', '_').replace('\\', '_')
                file_path = os.path.join(WATCH_FOLDER, file_name)
                
                with open(temp_path, 'rb') as src:
                    with open(file_path, 'wb') as dst:
                        dst.write(src.read())
                
                file_size = os.path.getsize(file_path) / 1024
                downloaded.append((file_name, file_size))
                
                logger.info(f"RSS torrent downloaded: {file_name} (from {user_name}, chat ID: {chat_id})")
                
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
            except Exception as e:
                logger.error(f"Error downloading {torrent_title}: {e}")
                failed.append(torrent_title)
        
        context.user_data['rss_selected'] = set()
        
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
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ *SUCCESS\\!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
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
