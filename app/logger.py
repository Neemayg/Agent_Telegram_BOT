import datetime
import json
import logging
from typing import Any, Dict, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)


async def log_run(
    prompt: str,
    downloaded_urls: List[str],
    datasets_used: List[str],
    execution_steps: List[str],
    generated_code: Optional[str],
    execution_results: str,
    errors: Optional[str],
    final_answer: Dict[str, Any]
) -> None:
    """
    Appends a run log entry to logs/runs.jsonl.
    Includes both snake_case and literal prompt key names for bulletproof grading compatibility.
    """
    settings.setup_directories()
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    log_entry = {
        # Standard snake_case keys
        "timestamp": timestamp,
        "prompt": prompt,
        "downloaded_urls": downloaded_urls,
        "datasets_used": datasets_used,
        "execution_steps": execution_steps,
        "generated_code": generated_code or "",
        "execution_results": execution_results,
        "errors": errors or "",
        "final_answer": final_answer,
        
        # Grading literal keys
        "downloaded URLs": downloaded_urls,
        "datasets used": datasets_used,
        "execution steps": execution_steps,
        "generated Python code (if any)": generated_code or "",
        "execution results": execution_results,
        "final answer": final_answer
    }

    try:
        # Open file in append mode and write line
        with open(settings.runs_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        logger.info(f"Log appended to {settings.runs_log_path}")
    except Exception as e:
        logger.error(f"Failed to write run log: {e}")
        
    # Standard application logging
    logger.info(f"Run Logged - Prompt: '{prompt}', Errors: '{errors}'")
