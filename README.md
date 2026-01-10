# Send Torrent Telegram Bot 🤖

A simple and secure Telegram bot that receives `.torrent` files and saves them to a shared folder monitored by your torrent client (qBittorrent, Transmission, etc.).

Perfect for managing your torrents remotely through Telegram!

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://telegram.org/)

## ✨ Features

- 🔒 **Secure**: Only authorized chat IDs can send torrents
- 👨‍👩‍👧‍👦 **Multi-user**: Support for multiple family members (comma-separated chat IDs)
- 🐳 **Dockerized**: Easy deployment with Docker Compose
- 🔄 **Auto-update**: Automatic Docker image builds on GitHub push
- 📦 **Lightweight**: Minimal Python dependencies
- 🚀 **Fast**: Instant torrent file transfer to your download manager
- 🔍 **Logging**: Complete activity logging for monitoring

## 📋 Prerequisites

- Docker and Docker Compose installed on your server
- A Telegram Bot Token ([Get one from @BotFather](https://t.me/botfather))
- A torrent client (qBittorrent, Transmission, etc.) with a watch folder configured

## 🚀 Quick Start

### 1. Get Your Telegram Chat ID

1. Start a conversation with [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your Chat ID (a number like `123456789`)
3. Save this number for the next step

### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/send-torrent-telegram-bot.git
cd send-torrent-telegram-bot
```

### 3. Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit the `.env` file with your values:

```env
# Get your bot token from @BotFather on Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Your Telegram Chat ID(s) - comma separated for multiple users
ALLOWED_CHAT_IDS=123456789,987654321

# Path to your torrent client's watch folder
TORRENT_WATCH_PATH=/path/to/qbittorrent/watch
```

### 4. Deploy with Docker Compose

```bash
docker-compose up -d
```

### 5. Verify the Bot is Running

```bash
docker logs send-torrent-telegram-bot
```

You should see: `Bot is running...`

## 💬 Using the Bot

1. Open Telegram and find your bot
2. Send `/start` to verify your chat ID and authorization
3. Send any `.torrent` file to the bot
4. The bot will save it to your watch folder
5. Your torrent client will automatically pick it up!

### Available Commands

- `/start` - Show welcome message and your chat ID
- `/help` - Show help information
- `/status` - Check bot status and authorization

## 🔧 Integration with Torrent Clients

### qBittorrent

1. In qBittorrent settings, enable "Automatically add torrents from"
2. Set the path to match your `TORRENT_WATCH_PATH`
3. (Optional) Enable "Delete .torrent files afterwards"

Example docker-compose for qBittorrent:

```yaml
version: '3.8'

services:
  qbittorrent:
    image: linuxserver/qbittorrent:latest
    container_name: qbittorrent
    volumes:
      - ./config:/config
      - ./downloads:/downloads
      - ./watch:/watch  # Same path as bot
    ports:
      - "8080:8080"
    restart: unless-stopped

  send-torrent-telegram-bot:
    image: ghcr.io/yourusername/send-torrent-telegram-bot:latest
    container_name: send-torrent-telegram-bot
    env_file:
      - .env
    volumes:
      - ./watch:/watch  # Shared folder
    restart: unless-stopped
```

### Transmission

Set the watch directory in Transmission settings:

```bash
transmission-remote --watch-dir /path/to/watch
transmission-remote --watch-dir-enabled
```

## 📦 Installing via Portainer

1. Go to your Portainer instance
2. Navigate to **Stacks** → **Add Stack**
3. Name it: `send-torrent-telegram-bot`
4. Paste the contents of `docker-compose.yml`
5. Add your environment variables in the "Environment variables" section
6. Click **Deploy the stack**

## 🔄 Auto-Updates

Every push to the `main` branch automatically:

1. Builds a new Docker image
2. Publishes it to GitHub Container Registry
3. Tags it as `latest`

To update your running bot:

```bash
docker-compose pull
docker-compose up -d
```

Or in Portainer: Click on your stack → **Pull and redeploy**

## 🛡️ Security Notes

- **Never commit your `.env` file** - it contains sensitive tokens
- Your bot token gives full control of your bot - keep it secret
- Only share your chat ID with trusted users
- The bot only accepts `.torrent` files from authorized chat IDs
- All unauthorized access attempts are logged

## 📝 Architecture

```
┌─────────────────┐
│  Telegram User  │
└────────┬────────┘
         │ .torrent file
         ▼
┌─────────────────────┐
│  Telegram Bot API   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Python Bot         │
│  (Docker Container) │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Shared Volume      │
│  /watch folder      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Torrent Client     │
│  (qBittorrent, etc) │
└─────────────────────┘
```

## 🐛 Troubleshooting

### Bot doesn't respond

- Check if the container is running: `docker ps`
- Check logs: `docker logs send-torrent-telegram-bot`
- Verify your bot token is correct
- Ensure the bot is not rate-limited by Telegram

### "Unauthorized" message

- Verify your chat ID is correct in `.env`
- Use `/start` command to see your actual chat ID
- Check for spaces in the `ALLOWED_CHAT_IDS` variable

### Torrents not being picked up by client

- Verify the watch folder path is correct on both sides
- Check folder permissions: `ls -la /path/to/watch`
- Ensure your torrent client is monitoring the folder
- Check torrent client logs

### Permission denied errors

```bash
sudo chown -R 1000:1000 /path/to/watch
sudo chmod -R 775 /path/to/watch
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Excellent Telegram Bot API wrapper
- The open-source community for inspiration and tools

## 📧 Support

If you encounter any issues or have questions:

1. Check the [Troubleshooting](#-troubleshooting) section
2. Search existing [GitHub Issues](https://github.com/yourusername/send-torrent-telegram-bot/issues)
3. Open a new issue with detailed information

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

<p align="left">
  <sub>100% built with GitHub Copilot (Claude Sonnet 4.5)</sub><br>
  <sub>Arturo Carretero Calvo — 2026</sub>
</p>