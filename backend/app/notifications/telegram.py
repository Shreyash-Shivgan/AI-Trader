from __future__ import annotations

import asyncio
from typing import Any

from telegram import Bot

from app.config import settings


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        self.token = token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        self.bot = Bot(token=self.token) if self.token else None

    async def send_message(self, message: str, parse_mode: str | None = None) -> None:
        if not self.bot or not self.chat_id:
            return
        await self.bot.send_message(
            chat_id=self.chat_id, text=message, parse_mode=parse_mode
        )

    def send_message_sync(self, message: str, parse_mode: str | None = None) -> None:
        asyncio.run(self.send_message(message, parse_mode=parse_mode))
