import asyncio
import pandas as pd
from app.executor import execute_code


def test_execute_code_success():
    async def run():
        code = """
df_filtered = test_df[test_df['val'] > 5]
result = df_filtered['val'].mean()
"""
        test_df = pd.DataFrame([{"name": "a", "val": 2}, {"name": "b", "val": 10}, {"name": "c", "val": 8}])
        context = {"test_df": test_df}
        
        result, stdout, error = await execute_code(code, context)
        
        assert error is None
        assert result == 9.0  # Mean of 10 and 8
    asyncio.run(run())


def test_execute_code_error():
    async def run():
        code = """
# Reference undefined variable to trigger error
result = undefined_variable + 2
"""
        context = {}
        result, stdout, error = await execute_code(code, context)
        
        assert error is not None
        assert "NameError" in error
        assert result is None
    asyncio.run(run())

