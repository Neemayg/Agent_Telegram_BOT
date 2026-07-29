import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Base path for resources
BASE_DIR = Path(__file__).resolve().parent.parent
RESOURCES_DIR = BASE_DIR / "app" / "resources"

# Map of dataset identifiers to their metadata (URL and local fallback)
DATASET_REGISTRY: Dict[str, Dict[str, str]] = {
    "mospi_unemployment": {
        "url": "https://raw.githubusercontent.com/neemaysmac/datasets/main/mospi_unemployment.csv",
        "local_path": str(RESOURCES_DIR / "mospi_unemployment.csv"),
    },
    "mospi_maternal_mortality": {
        "url": "https://raw.githubusercontent.com/neemaysmac/datasets/main/mospi_maternal_mortality.csv",
        "local_path": str(RESOURCES_DIR / "mospi_maternal_mortality.csv"),
    }
}


def resolve_local_dataset(name: str) -> Optional[Path]:
    """
    Checks if a dataset name exists in the local registry or resources directory.
    Returns the absolute path to the dataset if found, otherwise None.
    """
    normalized_name = name.lower().strip().replace(" ", "_")
    
    # 1. Direct registry check
    if normalized_name in DATASET_REGISTRY:
        local_path = Path(DATASET_REGISTRY[normalized_name]["local_path"])
        if local_path.exists():
            return local_path

    # 2. Fuzzy match in registry keys
    for key, meta in DATASET_REGISTRY.items():
        if key in normalized_name or normalized_name in key:
            local_path = Path(meta["local_path"])
            if local_path.exists():
                return local_path

    # 3. Direct check in resources directory
    for file in RESOURCES_DIR.glob("*"):
        if file.stem.lower() == normalized_name:
            return file

    logger.warning(f"Dataset '{name}' could not be resolved locally.")
    return None


def get_dataset_url(name: str) -> Optional[str]:
    """
    Gets the download URL for a dataset from the registry if available.
    """
    normalized_name = name.lower().strip().replace(" ", "_")
    if normalized_name in DATASET_REGISTRY:
        return DATASET_REGISTRY[normalized_name]["url"]
    
    for key, meta in DATASET_REGISTRY.items():
        if key in normalized_name or normalized_name in key:
            return meta["url"]
            
    return None
