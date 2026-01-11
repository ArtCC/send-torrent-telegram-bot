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
from bot.services import save_rss_url, delete_rss_url, get_rss_url


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
        "📡 Loading RSS feed\\.\\.\\.\\.\\.\n"
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


# ==================== RSS Callbacks ====================

async def handle_rss_browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle RSS browse and pagination callbacks."""
    query = update.callback_query
    chat_id = query.from_user.id
    
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
    
    # Determine current page
    if query.data.startswith("rss_page_"):
        try:
            page = int(query.data.split("_")[2])
            context.user_data['rss_current_page'] = page
        except (ValueError, IndexError):
            page = 0
    else:
        # First time browsing, start at page 0
        page = 0
        context.user_data['rss_current_page'] = page
        
        # Show loading
        await query.edit_message_text(
            "📡 Loading RSS feed\\.\\.\\.\\.\\.\n"
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
        
        # Store feed entries in context for callback
        context.user_data['rss_entries'] = feed.entries
        context.user_data['rss_feed_title'] = feed.feed.get('title', 'RSS Feed')
    
    # Get entries from context
    entries = context.user_data.get('rss_entries', [])
    feed_title = context.user_data.get('rss_feed_title', 'RSS Feed')
    
    # Initialize selection set if not exists
    if 'rss_selected' not in context.user_data:
        context.user_data['rss_selected'] = set()
    
    selected = context.user_data['rss_selected']
    
    # Pagination
    items_per_page = 15
    total_pages = math.ceil(len(entries) / items_per_page)
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(entries))
    page_entries = entries[start_idx:end_idx]
    
    # Create buttons for current page entries
    keyboard = []
    for i, entry in enumerate(page_entries):
        global_idx = start_idx + i
        title = entry.get('title', 'Unknown')
        category = entry.get('category', '')
        
        # Add emoji based on category
        emoji = "📺" if "series" in category.lower() else "🎬" if "pel" in category.lower() else "📦"
        
        # Add checkbox indicator
        checkbox = "✅" if global_idx in selected else "☐"
        
        # Truncate title if too long
        max_length = 55
        if len(title) > max_length:
            title = title[:max_length-3] + "..."
        
        keyboard.append([
            InlineKeyboardButton(
                f"{checkbox} {emoji} {title}",
                callback_data=f"rss_toggle_{global_idx}"
            )
        ])
    
    # Add download button if there are selections
    if selected:
        keyboard.append([
            InlineKeyboardButton(
                f"⬇️ Download ({len(selected)})",
                callback_data="rss_download_selected"
            )
        ])
    
    # Add navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            "◀️ Previous",
            callback_data=f"rss_page_{page-1}"
        ))
    
    # Page indicator
    nav_buttons.append(InlineKeyboardButton(
        f"📄 {page+1}/{total_pages}",
        callback_data="rss_page_info"
    ))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            "Next ▶️",
            callback_data=f"rss_page_{page+1}"
        ))
    
    keyboard.append(nav_buttons)
    
    # Add cancel button
    keyboard.append([
        InlineKeyboardButton("❌ Cancel", callback_data="rss_cancel")
    ])
    
    escaped_title = escape_markdown_v2(feed_title)
    total_text = f"{len(entries)} torrent" if len(entries) == 1 else f"{len(entries)} torrents"
    selected_text = f" \\| Selected: `{len(selected)}`" if selected else ""
    page_info = f"Page {page+1}/{total_pages} \\({start_idx+1}\\-{end_idx}\\)"
    
    try:
        await query.edit_message_text(
            "╔═══════════════════════╗\n"
            "      📡 *RSS FEED*      \n"
            "╚═══════════════════════╝\n\n"
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
        if "message is not modified" in str(e).lower():
            # Message content is identical, just answer the query
            await query.answer()
        else:
            raise


async def handle_rss_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle RSS torrent selection toggle."""
    query = update.callback_query
    chat_id = query.from_user.id
    
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
        
        # Get current page and entries
        page = context.user_data.get('rss_current_page', 0)
        entries = context.user_data.get('rss_entries', [])
        feed_title = context.user_data.get('rss_feed_title', 'RSS Feed')
        
        # Pagination
        items_per_page = 15
        total_pages = math.ceil(len(entries) / items_per_page)
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(entries))
        page_entries = entries[start_idx:end_idx]
        
        # Rebuild keyboard with updated selections
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
        
        # Add download button if there are selections
        if selected:
            keyboard.append([
                InlineKeyboardButton(
                    f"⬇️ Download ({len(selected)})",
                    callback_data="rss_download_selected"
                )
            ])
        
        # Add navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(
                "◀️ Previous",
                callback_data=f"rss_page_{page-1}"
            ))
        
        nav_buttons.append(InlineKeyboardButton(
            f"📄 {page+1}/{total_pages}",
            callback_data="rss_page_info"
        ))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(
                "Next ▶️",
                callback_data=f"rss_page_{page+1}"
            ))
        
        keyboard.append(nav_buttons)
        
        # Add cancel button
        keyboard.append([
            InlineKeyboardButton("❌ Cancel", callback_data="rss_cancel")
        ])
        
        escaped_title = escape_markdown_v2(feed_title)
        total_text = f"{len(entries)} torrent" if len(entries) == 1 else f"{len(entries)} torrents"
        selected_text = f" \\| Selected: `{len(selected)}`" if selected else ""
        page_info = f"Page {page+1}/{total_pages} \\({start_idx+1}\\-{end_idx}\\)"
        
        try:
            await query.edit_message_text(
                "╔═══════════════════════╗\n"
                "      📡 *RSS FEED*      \n"
                "╚═══════════════════════╝\n\n"
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
            if "message is not modified" in str(e).lower():
                # Message content is identical, ignore
                pass
            else:
                raise
        
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
