import subprocess
from urllib.parse import urljoin


def fetch_links(url: str, selector: str) -> list[str]:
    """Run curl | pup and return a deduplicated list of resolved URLs."""
    try:
        result = subprocess.run(
            f"curl -sL \"{url}\" | pup '{selector}'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return []

    seen = set()
    links = []
    for raw in result.stdout.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        resolved = urljoin(url, raw)
        if resolved not in seen:
            seen.add(resolved)
            links.append(resolved)
    return links
