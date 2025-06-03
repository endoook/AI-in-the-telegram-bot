md
# Telegram bot with CubikAI integration

This project allows you to deploy a Telegram bot with CubikAI AI model. The bot supports dialog, context processing, and advanced features of this model.

## Technology stack
- **Python 3.80+**
- `python-telegram-bot' v20+ (asynchronous version)
- **CubikAI** model (local)
- Redis (for caching and storing context)
- Docker (optional)

## env file
TELEGRAM_TOKEN=yours:token_bot # get from a botfather
CUBIKAI_MODEL_PATH=/path/CubikAI_v1.1.2
CUBIKAI_DEVICE=cuda #or cpu

## Quick Start

### 1. Cloning and configuration
```bash
git clone https://github.com/endoook/AI-in-the-telegram-bot.git
cd cubik-ai-telegram-bot
cp .env.example .env
