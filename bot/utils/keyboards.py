"""
Keyboard Utilities
Helper functions for creating inline keyboards.
"""

from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard(chat_id: Optional[int] = None, has_rss: bool = False) -> InlineKeyboardMarkup:
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
        [
            InlineKeyboardButton("👨‍💻 Author", callback_data="author"),
        ],
    ]
    
    # Add RSS button if user has RSS configured
    if has_rss:
        keyboard.append([
            InlineKeyboardButton("📡 Browse RSS Feed", callback_data="rss_browse")
        ])
    
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard with a back button."""
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
    return InlineKeyboardMarkup(keyboard)
