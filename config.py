import json
from constants import DEFAULT_CONFIG, CONFIG_PATH


def load_config() -> dict:
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            overrides = json.load(f)
        cfg.update(overrides)
    # Back-compat: allow a single "url" string key
    if not cfg["urls"] and "url" in cfg:
        cfg["urls"] = [cfg["url"]]
    return cfg


def parse_url_entries(urls_cfg: list) -> list[dict]:
    """Normalise the urls list into a uniform list of dicts."""
    entries = []
    for item in urls_cfg:
        if isinstance(item, str):
            entries.append({"name": item, "url": item})
        elif isinstance(item, dict) and "url" in item:
            entry = {
                "name": item.get("name", item["url"]),
                "url": item["url"],
            }
            for key in ("download_dir", "auto_unzip", "delete_after_unzip"):
                if key in item:
                    entry[key] = item[key]
            entries.append(entry)
    return entries


def resolve_config(global_cfg: dict, entry: dict) -> dict:
    """Merge per-URL overrides on top of the global config."""
    merged = global_cfg.copy()
    for key in ("download_dir", "auto_unzip", "delete_after_unzip"):
        if key in entry:
            merged[key] = entry[key]
    return merged
