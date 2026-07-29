import io
import json
import re
from typing import Optional
import pandas as pd

# Regular expressions to match structured data blocks
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\[\s*\{.*\}\s*\])\s*```", re.DOTALL | re.IGNORECASE)
JSON_RAW_RE = re.compile(r"(\[\s*\{\s*\"[^\"]+\"\s*:\s*.*\}\s*\])", re.DOTALL)
CSV_BLOCK_RE = re.compile(r"```(?:csv|text)?\s*\n(.*?)\n\s*```", re.DOTALL | re.IGNORECASE)
MD_TABLE_RE = re.compile(r"((?:\s*\|[^\n]+\|\s*(?:\n|$))+)", re.MULTILINE)


def clean_markdown_table(table_text: str) -> Optional[pd.DataFrame]:
    """
    Parses a markdown table into a Pandas DataFrame.
    """
    lines = [line.strip() for line in table_text.strip().split("\n") if line.strip()]
    if len(lines) < 2:
        return None

    # Filter out divider line (e.g., |---|---| or |:---|:---:|)
    cleaned_lines = []
    for line in lines:
        if re.match(r"^\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?$", line):
            continue
        cleaned_lines.append(line)

    if len(cleaned_lines) < 2:
        return None

    # Helper to split columns by '|'
    def split_row(row_str: str):
        parts = [p.strip() for p in row_str.split("|")]
        # If the row starts and/or ends with '|', remove the empty edge elements
        if parts and parts[0] == "":
            parts.pop(0)
        if parts and parts[-1] == "":
            parts.pop()
        return parts

    headers = split_row(cleaned_lines[0])
    rows = [split_row(line) for line in cleaned_lines[1:]]

    # Align rows to header size
    aligned_rows = []
    for row in rows:
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        elif len(row) > len(headers):
            row = row[:len(headers)]
        aligned_rows.append(row)

    try:
        df = pd.DataFrame(aligned_rows, columns=headers)
        # Attempt to convert numeric columns
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col].str.replace(",", ""), errors="raise")
            except Exception:
                pass
        return df
    except Exception:
        return None


def parse_embedded_data(text: str) -> Optional[pd.DataFrame]:
    """
    Inspects text for embedded datasets (JSON blocks, CSV blocks, Markdown tables)
    and parses the first matching block into a Pandas DataFrame.
    """
    # 1. Try to match JSON blocks or raw JSON array
    json_match = JSON_BLOCK_RE.search(text) or JSON_RAW_RE.search(text)
    if json_match:
        try:
            raw_json = json_match.group(1).strip()
            data = json.loads(raw_json)
            df = pd.DataFrame(data)
            return df
        except Exception:
            pass

    # 2. Try to match Markdown tables
    md_match = MD_TABLE_RE.search(text)
    if md_match:
        df = clean_markdown_table(md_match.group(1))
        if df is not None and not df.empty:
            return df

    # 3. Try to match fenced CSV blocks
    csv_match = CSV_BLOCK_RE.search(text)
    if csv_match:
        try:
            csv_lines = [line.strip() for line in csv_match.group(1).strip().split("\n")]
            csv_data = "\n".join(csv_lines)
            df = pd.read_csv(io.StringIO(csv_data), skipinitialspace=True)
            return df
        except Exception:
            pass

    # 4. Fallback: Parse whole message as CSV if it has headers and multiple lines with commas
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) >= 2 and any("," in line for line in lines):
        try:
            # Simple check if lines have similar comma count
            comma_counts = [line.count(",") for line in lines[:3]]
            if len(set(comma_counts)) == 1 or (max(comma_counts) - min(comma_counts) <= 1):
                df = pd.read_csv(io.StringIO(text.strip()))
                if not df.empty and len(df.columns) > 1:
                    return df
        except Exception:
            pass

    return None
