from fastapi import APIRouter

from app.core.config import settings
from app.services.langfuse_service import is_langfuse_configured, langfuse_host

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/status")
async def integration_status():
    telegram_configured = bool(settings.TELEGRAM_BOT_TOKEN)
    telegram_polling = telegram_configured and settings.TELEGRAM_POLLING_ENABLED
    return {
        "telegram": {
            "configured": telegram_configured,
            "polling_enabled": settings.TELEGRAM_POLLING_ENABLED,
            "status": "polling" if telegram_polling else "disabled",
            "mode": "long_polling",
            "channel": "telegram",
            "chat_scope": "private",
            "route": "default_workflow",
        },
        "langfuse": {
            "configured": is_langfuse_configured(),
            "status": "configured" if is_langfuse_configured() else "disabled",
            "host": langfuse_host() or None,
        }
    }
