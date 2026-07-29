import asyncio
import contextlib
import io
import sys
from typing import Any, Dict, Optional, Tuple
import duckdb
import numpy as np
import pandas as pd


def _sync_execute_code(code: str, context: Dict[str, Any]) -> Tuple[Optional[Any], str, Optional[str]]:
    """
    Synchronous execution wrapper. Captures stdout and handles exceptions.
    """
    stdout_buffer = io.StringIO()
    error_msg: Optional[str] = None
    result: Optional[Any] = None

    # Merge libraries and custom execution variables
    execution_globals = {
        "pd": pd,
        "np": np,
        "duckdb": duckdb,
        **context
    }
    execution_locals: Dict[str, Any] = {}

    try:
        with contextlib.redirect_stdout(stdout_buffer):
            # Execute the code block
            exec(code, execution_globals, execution_locals)
            
        # Extract the expected result from locals or globals
        result = execution_locals.get("result") or execution_globals.get("result")
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"

    stdout_content = stdout_buffer.getvalue()
    return result, stdout_content, error_msg


async def execute_code(code: str, context: Dict[str, Any]) -> Tuple[Optional[Any], str, Optional[str]]:
    """
    Executes Python code asynchronously in a separate worker thread.
    Returns (result, stdout, error).
    """
    # Use asyncio.to_thread to prevent blocking the event loop during heavy operations
    return await asyncio.to_thread(_sync_execute_code, code, context)
