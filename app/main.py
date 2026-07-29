import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from telegram import Update

from app.config import settings
from app.telegram_bot import get_telegram_app

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events, managing the Telegram bot lifecycle.
    """
    settings.setup_directories()
    
    # Touch log file so it is guaranteed to exist for grading
    if not settings.runs_log_path.exists():
        settings.runs_log_path.write_text("")

    # Initialize Telegram Bot Application
    bot_app = get_telegram_app()
    await bot_app.initialize()

    if settings.BASE_URL:
        # Webhook mode: Telegram will push updates to our server
        webhook_url = f"{settings.BASE_URL.rstrip('/')}/telegram-webhook"
        await bot_app.bot.set_webhook(url=webhook_url)
        # Start the bot engine (required before process_update is active)
        await bot_app.start()
        logger.info(f"Bot started in WEBHOOK mode at {webhook_url}")
    else:
        # Polling mode: Local development background polling
        await bot_app.start()
        await bot_app.updater.start_polling()
        logger.info("Bot started in POLLING mode in background.")

    yield

    # Shutdown bot resources cleanly
    logger.info("Shutting down Telegram Bot Application...")
    bot_app = get_telegram_app()
    if bot_app.updater and bot_app.updater.running:
        await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Data Analyst Telegram Bot",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    """
    Health check endpoint for container platform orchestration (e.g. Railway).
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "bot_mode": "webhook" if settings.BASE_URL else "polling",
            "port": settings.PORT
        }
    )


@app.get("/run.jsonl")
async def serve_run_log():
    """
    Grading endpoint: Serves the public runs log.
    Guarantees a file response even if no logs have been written yet.
    """
    if not settings.runs_log_path.exists():
        settings.setup_directories()
        settings.runs_log_path.write_text("")
        
    return FileResponse(
        path=settings.runs_log_path,
        media_type="application/x-jsonlines",
        filename="runs.jsonl"
    )


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    """
    Webhook target endpoint. Receives updates from Telegram and delegates to PTB.
    """
    bot_app = get_telegram_app()
    if not bot_app.running:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content="Bot app is not running.")
        
    try:
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        return Response(status_code=status.HTTP_200_OK, content="OK")
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}")
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=str(e))


if __name__ == "__main__":
    import uvicorn
    # Use binding configuration defined in settings
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False  # Disabled in production
    )
