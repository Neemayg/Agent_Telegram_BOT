import pandas as pd
from app.parser import parse_embedded_data, clean_markdown_table


def test_clean_markdown_table():
    md_table = """
    | State | Maternal Mortality |
    |---|---|
    | Assam | 215 |
    | Delhi | 110 |
    """
    df = clean_markdown_table(md_table)
    assert df is not None
    assert not df.empty
    assert list(df.columns) == ["State", "Maternal Mortality"]
    assert df.iloc[0]["State"] == "Assam"
    # Verify numeric conversion was attempted
    assert df.iloc[0]["Maternal Mortality"] == 215


def test_parse_embedded_json():
    json_text = """
    Below is the requested JSON format:
    ```json
    [
        {"state": "Delhi", "unemployment_rate": 8.5},
        {"state": "Maharashtra", "unemployment_rate": 6.1}
    ]
    ```
    Please analyze it.
    """
    df = parse_embedded_data(json_text)
    assert df is not None
    assert len(df) == 2
    assert df.iloc[0]["state"] == "Delhi"


def test_parse_embedded_csv():
    csv_text = """
    Here is the CSV:
    ```csv
    state,unemployment_rate
    Delhi,8.5
    Maharashtra,6.1
    ```
    """
    df = parse_embedded_data(csv_text)
    assert df is not None
    assert len(df) == 2
    assert df.iloc[0]["state"] == "Delhi"


def test_parse_raw_csv():
    raw_csv = """state,unemployment_rate
Delhi,8.5
Maharashtra,6.1"""
    df = parse_embedded_data(raw_csv)
    assert df is not None
    assert len(df) == 2
    assert df.iloc[0]["state"] == "Delhi"
