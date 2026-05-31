import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import IO

from telegram.error import Conflict
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.core.config import settings
from app.core.database import async_session
from app.services.workflow_service import execute_workflow_run

logger = logging.getLogger(__name__)


def _acquire_polling_lock() -> IO[str] | None:
    lock_path = Path(tempfile.gettempdir()) / "yuno-telegram-polling.lock"
    lock_file = lock_path.open("a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return None
    return lock_file


def _release_polling_lock(lock_file: IO[str]) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        lock_file.close()


def clean_telegram_reply(text: str) -> str:
    reply = text.strip()
    reply = re.sub(r"\n{3,}", "\n\n", reply)
    reply = re.sub(r"^\s*#{1,6}\s+", "", reply, flags=re.MULTILINE)
    reply = re.sub(r"\*\*(.*?)\*\*", r"\1", reply)
    reply = re.sub(r"\n\s*\*\s+", "\n- ", reply)
    reply = re.sub(r"^[ \t]+", "", reply, flags=re.MULTILINE)
    return reply[:3900].strip()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("Hello! Send me a message and I will route it through your agents.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if update.message.chat.type != "private":
        return

    chat_id = update.message.chat_id
    try:
        async with async_session() as db:
            result = await execute_workflow_run(
                update.message.text,
                channel="telegram",
                user_id=str(chat_id),
                db=db,
            )
        if result.reply_to_channel:
            reply = clean_telegram_reply(result.response or "The workflow finished with no output.")
            await update.message.reply_text(reply)
    except Exception:
        logger.exception("Telegram workflow execution failed")
        await update.message.reply_text("Something went wrong while processing your request.")


def build_application() -> Application:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set")
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


async def start_polling() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.info("TELEGRAM_BOT_TOKEN is empty; Telegram bot disabled.")
        await asyncio.Event().wait()

    lock_file = _acquire_polling_lock()
    if lock_file is None:
        logger.warning("Telegram polling already owns the local lock; this process will not poll.")
        await asyncio.Event().wait()

    application = build_application()
    try:
        await application.initialize()
        await application.start()
        if application.updater is None:
            raise RuntimeError("Telegram updater is not available")
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        try:
            await asyncio.Event().wait()
        except Conflict:
            logger.exception("Telegram polling conflict; another bot consumer is already running.")
            await asyncio.Event().wait()
    finally:
        if application.updater is not None and application.updater.running:
            await application.updater.stop()
        if application.running:
            await application.stop()
        await application.shutdown()
        _release_polling_lock(lock_file)
