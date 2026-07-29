import pytest
from app.downloader import get_cache_filename


def test_get_cache_filename_csv():
    url = "https://example.com/data/report.csv?query=1"
    filename = get_cache_filename(url)
    assert filename.endswith(".csv")
    assert len(filename) > 4


def test_get_cache_filename_xlsx():
    url = "https://example.com/data/report.xlsx"
    filename = get_cache_filename(url)
    assert filename.endswith(".xlsx")


def test_get_cache_filename_unsupported():
    # Unsupported extensions default to .csv
    url = "https://example.com/data/report.txt"
    filename = get_cache_filename(url)
    assert filename.endswith(".csv")
