
# Telegram bot with CubikAI integration

This project allows you to deploy a Telegram bot with CubikAI AI model. The bot supports dialog, context processing, and advanced features of this model.

## Technology stack
- **Python 3.80+**
- `python-telegram-bot' v20+ (asynchronous version)
- **CubikAI** model (local)
- Redis (for caching and storing context)
- Docker (optional)

## .env file
TELEGRAM_TOKEN=yours:token_bot # get from a botfather

CUBIKAI_MODEL_PATH=/path/CubikAI_v1.1.2

CUBIKAI_DEVICE=cuda (NVIDIA only) #or CPU

## pips
```bash
pip install python-telegram-bot==13.7 requests==2.28.1 python-dotenv==1.0.0 flask==2.0.3 python-docx==0.8.11 PyPDF2==3.0.1 -y
```

## Quick Start
You can change the local AI model to any one that suits you
but you will have to change the generation code
Read LICENSE 

### 1. Cloning and configuration
```bash
git clone https://github.com/endoook/AI-in-the-telegram-bot.git
cd cubik-ai-telegram-bot
cp .env.example .env
```
