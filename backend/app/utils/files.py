from pathlib import Path


def file_exists(path: str) -> bool:
    try:
        return Path(path).expanduser().resolve().exists()
    except Exception:
        return False


def safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)
