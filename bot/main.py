#!/usr/bin/env python3
"""
Telegram Torrent Bot
Receives .torrent files and saves them to a shared folder for torrent clients.
"""

import os
import logging
from pathlib import Path
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


def is_authorized(chat_id: int) -> bool:
    """Check if the chat ID is authorized to use the bot."""
    return chat_id in ALLOWED_CHAT_IDS


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
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
        welcome_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard()
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
        "🔍 `/menu` \\- Show interactive menu\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Quick Actions:*\n\n"
        "• Send any `.torrent` file\n"
        "• Use the menu buttons\n"
        "• Check your authorization\n\n"
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

    # Send processing message
    processing_msg = await update.message.reply_text(
        "⏳ *Processing\\.\\.\\.*\n\n" "📥 Receiving your torrent file\\.\\.\\.",
        parse_mode="MarkdownV2",
    )

    try:
        # Download the file
        file = await context.bot.get_file(document.file_id)
        file_path = os.path.join(WATCH_FOLDER, file_name)

        await file.download_to_drive(file_path)

        logger.info(f"Torrent file saved: {file_name} (from {user_name}, chat ID: {chat_id})")

        # Delete processing message
        await processing_msg.delete()

        # Send success message
        success_message = (
            f"╔═══════════════════════╗\n"
            f"      ✅ *SUCCESS\\!*      \n"
            f"╚═══════════════════════╝\n\n"
            f"🎉 Torrent received and saved\\!\n\n"
            f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
            f"  📁 *File Details*\n"
            f"  • Name: `{file_name}`\n"
            f"  • Size: `{file_size:.2f} KB`\n"
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

        await update.message.reply_text(
            success_message, parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error saving torrent file: {e}")

        # Delete processing message
        try:
            await processing_msg.delete()
        except:
            pass

        keyboard = [[InlineKeyboardButton("🔄 Try Again", callback_data="menu")]]
        await update.message.reply_text(
            "╔═══════════════════════╗\n"
            "        ❌ *ERROR*        \n"
            "╚═══════════════════════╝\n\n"
            "⚠️ Failed to save the torrent\n"
            "file\\. Please try again\\.\n\n"
            "🔧 If the problem persists,\n"
            "contact the administrator\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu command."""
    menu_message = (
        "╔═══════════════════════╗\n"
        "       🎯 *MAIN MENU*       \n"
        "╚═══════════════════════╝\n\n"
        "Select an option below:\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    await update.message.reply_text(
        menu_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard()
    )


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
            menu_message, parse_mode="MarkdownV2", reply_markup=get_main_menu_keyboard()
        )

    elif query.data == "help":
        help_message = (
            "╔═══════════════════════╗\n"
            "       📖 *HELP GUIDE*       \n"
            "╚═══════════════════════╝\n\n"
            "*Available Commands:*\n\n"
            "🏠 `/start` \\- Main menu \\& welcome\n"
            "❓ `/help` \\- Show this help guide\n"
            "📊 `/status` \\- Check bot status\n"
            "🔍 `/menu` \\- Show interactive menu\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "*Quick Actions:*\n\n"
            "• Send any `.torrent` file\n"
            "• Use the menu buttons\n"
            "• Check your authorization\n\n"
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
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_other_messages))

    # Start the bot
    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
