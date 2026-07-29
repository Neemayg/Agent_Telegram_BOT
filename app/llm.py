import logging
from typing import Any, Dict, List, Optional
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from app.config import settings
from app.prompts import INTERPRETER_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Initialize OpenAI Client
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY or "mock-key")


# 1. Pydantic schema for Planner Phase
class DataAnalysisPlan(BaseModel):
    reasoning: str = Field(description="Step-by-step reasoning about the request and historical context.")
    urls_to_download: List[str] = Field(default=[], description="List of dataset URLs that need to be downloaded.")
    datasets_needed: List[str] = Field(default=[], description="List of catalog dataset identifiers required (e.g. 'mospi_unemployment', 'mospi_maternal_mortality').")
    python_code: Optional[str] = Field(None, description="Executable Python code using pandas/duckdb to perform data analysis. Assign final result to the variable 'result'.")
    explanation_if_missing: Optional[str] = Field(None, description="Explanation text if data or URL cannot be resolved.")


# 2. Pydantic schema for Interpreter Phase
class FinalAnswerInterpretation(BaseModel):
    reasoning: str = Field(description="Interpretation of the execution outcome.")
    answer: Dict[str, Any] = Field(
        description="The final answer object matching the requested schema. If no schema is requested, format as a general dictionary like {'result': <value>}."
    )


async def generate_plan(messages: List[Dict[str, str]]) -> DataAnalysisPlan:
    """
    Calls OpenAI to analyze the chat history and generate a structured data analysis plan.
    """
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not configured.")
        return DataAnalysisPlan(
            reasoning="OpenAI API key missing.",
            explanation_if_missing="API configuration error: OpenAI API Key is missing."
        )

    # Format the prompt messages
    prompt_messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        *messages
    ]

    try:
        completion = await openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",  # Using cost-efficient, fast gpt-4o-mini
            messages=prompt_messages,
            response_format=DataAnalysisPlan,
            timeout=45.0
        )
        plan = completion.choices[0].message.parsed
        if plan:
            logger.info(f"Generated Plan: {plan.reasoning[:100]}...")
            return plan
        raise Exception("OpenAI returned an empty plan.")
    except Exception as e:
        logger.exception("Failed to generate plan via OpenAI")
        return DataAnalysisPlan(
            reasoning=f"OpenAI error: {str(e)}",
            explanation_if_missing=f"Error generating data analysis plan: {str(e)}"
        )


async def interpret_result(
    messages: List[Dict[str, str]],
    code: Optional[str],
    result_val: Any,
    stdout: str,
    error: Optional[str]
) -> Dict[str, Any]:
    """
    Calls OpenAI to interpret the results of code execution and format the final answer.
    """
    if not settings.OPENAI_API_KEY:
        return {"error": "API configuration error: OpenAI API Key is missing."}

    # Format context for interpreter
    interpreter_input = (
        f"Conversation history: {messages}\n\n"
        f"Generated Code:\n{code}\n\n"
        f"Execution Result (result variable): {result_val}\n"
        f"Execution Stdout:\n{stdout}\n"
        f"Execution Errors: {error}\n"
    )

    prompt_messages = [
        {"role": "system", "content": INTERPRETER_SYSTEM_PROMPT},
        {"role": "user", "content": interpreter_input}
    ]

    try:
        completion = await openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=prompt_messages,
            response_format=FinalAnswerInterpretation,
            timeout=30.0
        )
        interpretation = completion.choices[0].message.parsed
        if interpretation:
            logger.info(f"Generated Interpretation: {interpretation.reasoning[:100]}...")
            return interpretation.answer
        raise Exception("OpenAI returned empty interpretation.")
    except Exception as e:
        logger.exception("Failed to interpret results via OpenAI")
        # Return fallback error dictionary
        return {"error": f"Error interpreting execution results: {str(e)}"}
