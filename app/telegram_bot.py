import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import settings
from app.datasets import get_dataset_url, resolve_local_dataset
from app.downloader import download_file
from app.executor import execute_code
from app.llm import generate_plan, interpret_result
from app.logger import log_run
from app.parser import parse_embedded_data

logger = logging.getLogger(__name__)

# Global thread-safe/async-safe chat history manager
# Using local JSON file storage for stability across restarts
_history_cache: Dict[int, List[Dict[str, str]]] = {}


def load_chat_history() -> Dict[str, List[Dict[str, str]]]:
    """Loads all chat histories from logs/chat_history.json."""
    settings.setup_directories()
    if settings.chat_history_path.exists():
        try:
            with open(settings.chat_history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load chat history: {e}")
    return {}


def save_all_chat_histories(histories: Dict[str, List[Dict[str, str]]]) -> None:
    """Saves all chat histories to logs/chat_history.json."""
    settings.setup_directories()
    try:
        # Atomic write
        temp_path = settings.chat_history_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(histories, f, indent=2)
        temp_path.rename(settings.chat_history_path)
    except Exception as e:
        logger.error(f"Failed to save chat history: {e}")


def get_history(chat_id: int) -> List[Dict[str, str]]:
    """Retrieves conversation history for a given chat_id."""
    chat_str = str(chat_id)
    histories = load_chat_history()
    return histories.get(chat_str, [])


def save_history(chat_id: int, history: List[Dict[str, str]]) -> None:
    """Updates and saves conversation history for a given chat_id."""
    chat_str = str(chat_id)
    histories = load_chat_history()
    histories[chat_str] = history
    save_all_chat_histories(histories)


def clear_history(chat_id: int) -> None:
    """Clears history for a chat_id."""
    chat_str = str(chat_id)
    histories = load_chat_history()
    if chat_str in histories:
        del histories[chat_str]
        save_all_chat_histories(histories)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the /start command. Resets history."""
    if update.effective_chat:
        chat_id = update.effective_chat.id
        clear_history(chat_id)
        # We reply with a clean start message in JSON format to remain uniform.
        base_url = settings.BASE_URL or f"http://localhost:{settings.PORT}"
        log_url = f"{base_url.rstrip('/')}/run.jsonl"
        response = {
            "answer": {"message": "Data Analyst Bot initialized. Send your questions to begin."},
            "log_url": log_url
        }
        await update.message.reply_text(json.dumps(response, indent=2))


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the /clear command."""
    if update.effective_chat:
        chat_id = update.effective_chat.id
        clear_history(chat_id)
        base_url = settings.BASE_URL or f"http://localhost:{settings.PORT}"
        log_url = f"{base_url.rstrip('/')}/run.jsonl"
        response = {
            "answer": {"message": "Conversation history cleared."},
            "log_url": log_url
        }
        await update.message.reply_text(json.dumps(response, indent=2))


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Main handler for text messages. Performs analysis and responds with formatted JSON.
    """
    if not update.message or not update.message.text or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_prompt = update.message.text
    
    # Initialize log variables
    downloaded_urls: List[str] = []
    datasets_used: List[str] = []
    execution_steps: List[str] = ["Received request."]
    generated_code: Optional[str] = None
    execution_results: str = ""
    errors: Optional[str] = None
    final_answer: Dict[str, Any] = {}

    # Define base log URL
    base_url = settings.BASE_URL or f"http://localhost:{settings.PORT}"
    log_url = f"{base_url.rstrip('/')}/run.jsonl"

    try:
        # 1. Update multi-turn chat history
        history = get_history(chat_id)
        history.append({"role": "user", "content": user_prompt})
        execution_steps.append("Updated conversation history.")

        # 2. Check for embedded table/CSV data in user's prompt
        embedded_df = parse_embedded_data(user_prompt)
        execution_context: Dict[str, Any] = {}
        if embedded_df is not None:
            # Cache it locally and pre-load into sandbox context
            embedded_path = settings.CACHE_DIR / "embedded_data.csv"
            embedded_df.to_csv(embedded_path, index=False)
            execution_context["embedded_data"] = embedded_df
            datasets_used.append("embedded_data")
            execution_steps.append("Pasted/embedded dataset detected and loaded into execution context.")

        # 3. Call LLM Planner to generate the analysis plan and code
        plan = await generate_plan(history)
        execution_steps.append(f"Generated analysis plan: {plan.reasoning[:120]}...")
        
        # Determine URLs to download
        if plan.urls_to_download:
            execution_steps.append(f"Downloading required URLs: {plan.urls_to_download}")
            for url in plan.urls_to_download:
                try:
                    local_path = await download_file(url)
                    downloaded_urls.append(url)
                    # Expose to python code: load the dataset
                    name = Path(local_path).stem.lower().replace(" ", "_")
                    df = pd.read_csv(local_path)
                    execution_context[name] = df
                    datasets_used.append(name)
                except Exception as ex:
                    errors = f"Failed to download URL {url}: {ex}"
                    execution_steps.append(errors)
                    raise ex

        # Resolve named datasets needed from the catalog
        if plan.datasets_needed:
            execution_steps.append(f"Resolving required catalog datasets: {plan.datasets_needed}")
            for ds in plan.datasets_needed:
                local_path = resolve_local_dataset(ds)
                if local_path and local_path.exists():
                    df = pd.read_csv(local_path)
                    execution_context[ds] = df
                    datasets_used.append(ds)
                else:
                    # Try to fetch download URL if registered
                    url = get_dataset_url(ds)
                    if url:
                        try:
                            local_path = await download_file(url)
                            downloaded_urls.append(url)
                            df = pd.read_csv(local_path)
                            execution_context[ds] = df
                            datasets_used.append(ds)
                        except Exception as ex:
                            errors = f"Failed resolving catalog dataset '{ds}' via URL: {ex}"
                            execution_steps.append(errors)
                            raise ex
                    else:
                        errors = f"Dataset not found: {ds}"
                        execution_steps.append(errors)
                        raise FileNotFoundError(errors)

        # 4. Sandbox Python execution
        if plan.python_code:
            generated_code = plan.python_code
            execution_steps.append("Running analysis code in sandbox.")
            result_val, stdout, err = await execute_code(generated_code, execution_context)
            
            if err:
                errors = err
                execution_steps.append(f"Sandbox execution failed: {err}")
                execution_results = stdout
            else:
                execution_steps.append("Sandbox execution completed successfully.")
                execution_results = f"Stdout: {stdout}\nResult variable: {result_val}"
                
            # 5. LLM Interpretation & Formatting
            final_answer = await interpret_result(
                history, generated_code, result_val, stdout, err
            )
            execution_steps.append("Interpreted results and formatted response.")
        else:
            # Plan contains no executable code (e.g. data missing or error in planning)
            final_answer = {"error": plan.explanation_if_missing or "No analysis code generated."}
            execution_steps.append("No analysis code to run. Formulated explanation.")

        # Update chatbot response history
        history.append({"role": "assistant", "content": json.dumps(final_answer)})
        save_history(chat_id, history)

    except Exception as e:
        logger.exception("Error handling Telegram message")
        if not errors:
            errors = f"{type(e).__name__}: {str(e)}"
        final_answer = {"error": f"Internal process failed: {errors}"}
        execution_steps.append(f"Error caught: {errors}")

    # Ensure valid final_answer structure
    if not isinstance(final_answer, dict):
        final_answer = {"result": final_answer}

    # Format the exact required response
    telegram_response = {
        "answer": final_answer,
        "log_url": log_url
    }

    # 6. Send message to Telegram
    try:
        response_text = json.dumps(telegram_response, indent=2)
        await update.message.reply_text(response_text)
    except Exception as e:
        logger.error(f"Failed to send response to Telegram user: {e}")

    # 7. Write run log entry asynchronously
    await log_run(
        prompt=user_prompt,
        downloaded_urls=downloaded_urls,
        datasets_used=datasets_used,
        execution_steps=execution_steps,
        generated_code=generated_code,
        execution_results=execution_results,
        errors=errors,
        final_answer=telegram_response
    )


# Bot instance global holder
_bot_app: Optional[Application] = None


def get_telegram_app() -> Application:
    """Initializes and returns the singleton PTB Application."""
    global _bot_app
    if _bot_app is None:
        token = settings.BOT_TOKEN or "123456:dummy-token-for-testing"
        # Instantiate application
        _bot_app = Application.builder().token(token).build()
        
        # Register handlers
        _bot_app.add_handler(CommandHandler("start", start_command))
        _bot_app.add_handler(CommandHandler("clear", clear_command))
        _bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        logger.info("Telegram Bot Application initialized.")
        
    return _bot_app
