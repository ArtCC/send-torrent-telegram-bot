"""
Keyboard Utilities
Helper functions for creating bot keyboards.
"""

from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


BTN_START = "🏠 Start"
BTN_HELP = "📖 Help"
BTN_STATUS = "📊 Status"
BTN_BROWSE_RSS = "📡 Browse RSS"


def get_persistent_keyboard(has_rss: bool = False) -> ReplyKeyboardMarkup:
    """Create the always-available reply keyboard for global navigation."""
    keyboard = [
        [KeyboardButton(BTN_START), KeyboardButton(BTN_HELP)],
        [KeyboardButton(BTN_STATUS)],
    ]

    if has_rss:
        keyboard.append([KeyboardButton(BTN_BROWSE_RSS)])

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Choose an action or send a .torrent file",
    )


def get_main_menu_keyboard(chat_id: Optional[int] = None, has_rss: bool = False) -> InlineKeyboardMarkup:
    """Create the main menu keyboard with inline buttons."""
    keyboard = [
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
            InlineKeyboardButton("📊 Status", callback_data="status"),
        ],
        [
            InlineKeyboardButton("📋 How to Use", callback_data="howto"),
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
