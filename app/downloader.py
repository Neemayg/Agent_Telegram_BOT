import aiohttp
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse
from app.config import settings

logger = logging.getLogger(__name__)


def get_cache_filename(url: str) -> str:
    """
    Generates a deterministic filename based on the MD5 hash of the URL.
    Attempts to preserve the original file extension if present in the path.
    """
    parsed_url = urlparse(url)
    ext = Path(parsed_url.path).suffix
    # Restrict extensions to standard data formats
    if ext.lower() not in [".csv", ".xlsx", ".xls", ".json"]:
        ext = ".csv"  # Default fallback
        
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    return f"{url_hash}{ext}"


async def download_file(url: str, force_download: bool = False) -> Path:
    """
    Downloads a file asynchronously from a URL and caches it locally.
    If the file exists in the cache, it returns the cached path unless force_download is True.
    """
    settings.setup_directories()
    filename = get_cache_filename(url)
    cache_path = settings.CACHE_DIR / filename

    if cache_path.exists() and not force_download:
        logger.info(f"Using cached file for URL: {url} -> {cache_path}")
        return cache_path

    logger.info(f"Downloading from URL: {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=30) as response:
            if response.status != 200:
                raise Exception(f"Failed to download file from {url}. Status code: {response.status}")
            
            # Read content and write to temp file, then rename atomically
            content = await response.read()
            temp_path = cache_path.with_suffix(".tmp")
            temp_path.write_bytes(content)
            temp_path.rename(cache_path)
            
            logger.info(f"Successfully downloaded and cached: {url} -> {cache_path}")
            return cache_path
