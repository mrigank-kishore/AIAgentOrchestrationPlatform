import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from app.core.config import settings
from app.services.workflow_service import execute_workflow

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    await update.message.reply_text(
        "👋 Hello! I'm your AI agent. Send me a message and I'll get to work."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Main handler for all text messages.
    Triggers the workflow linked to this Telegram channel and replies with the result.
    """
    chat_id = update.message.chat_id
    user_text = update.message.text

    # Only respond to private chats (simplifies the demo)
    if update.message.chat.type != "private":
        return

    logger.info(f"Received message from {chat_id}: {user_text[:50]}...")

    try:
        # Execute the whole workflow (asynchronous) and wait for final output
        result = await execute_workflow(
            user_message=user_text,
            channel="telegram",
            user_id=str(chat_id),
        )
        reply = result if result else "⚠️ The workflow finished with no output."
    except Exception as e:
        logger.exception("Workflow execution failed")
        reply = f"❌ Something went wrong while processing your request. Error: {str(e)}"

    # Send the final answer back to the user
    await update.message.reply_text(reply)

# ------------------------------------------------------------------
# Bot setup & lifecycle
# ------------------------------------------------------------------
def build_application() -> Application:
    """Create and configure the Telegram bot application."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment")

    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return application

async def start_polling() -> None:
    """
    Launch the bot in long‑polling mode.
    This function is meant to be run as a background task inside the FastAPI lifespan.
    """
    logger.info("Starting Telegram bot (polling mode)...")
    app = build_application()

    # Important: close_loop=False prevents run_polling from shutting down the event loop
    # after the bot stops (which would break the FastAPI server)
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    logger.info("Telegram bot is ready and polling.")

    # Keep the task alive – we rely on FastAPI lifespan to cancel it later
    # We'll block forever on a simple Event that will never be set.
    import asyncio
    stop_event = asyncio.Event()
    await stop_event.wait()