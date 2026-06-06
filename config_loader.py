from pathlib import Path
import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

def load_config(path: str | None = None) -> dict:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"No existe config.yaml en: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
