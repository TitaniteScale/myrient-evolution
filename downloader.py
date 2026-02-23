import logging
import subprocess
import threading
import zipfile
from pathlib import Path
from urllib.parse import unquote

from constants import SPINNER

# ---------------------------------------------------------------------------
# Logging — writes to happy-crush.log next to this file
# ---------------------------------------------------------------------------

LOG_PATH = Path(__file__).parent / "happy-crush.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
log = logging.getLogger("happy-crush")


def download_file(url: str, dest_dir: str) -> "Path | None":
    """Download *url* into *dest_dir* using wget. Returns the local path or None."""
    dest = Path(dest_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    log.info("Starting download: %s -> %s", url, dest)

    proc = subprocess.run(
        ["wget", "--no-verbose", "-P", str(dest), url],
        capture_output=True,
        text=True,
    )

    if proc.stdout.strip():
        log.debug("wget stdout: %s", proc.stdout.strip())
    if proc.stderr.strip():
        log.debug("wget stderr: %s", proc.stderr.strip())

    if proc.returncode != 0:
        log.error(
            "wget exited with code %d for URL: %s\nstderr: %s",
            proc.returncode, url, proc.stderr.strip(),
        )
        return None

    # wget decodes percent-encoding when saving, so we must do the same
    # before checking whether the file exists on disk.
    raw_name = url.split("?")[0].rstrip("/").split("/")[-1]
    filename  = unquote(raw_name)
    candidate = dest / filename

    log.debug("Expecting file at: %s  (exists=%s)", candidate, candidate.exists())

    if candidate.exists():
        log.info("Download complete: %s", candidate)
        return candidate

    # Fallback: scan dest for the most recently modified file as a last resort
    files = sorted(dest.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    recent = next((p for p in files if p.is_file()), None)
    if recent:
        log.warning(
            "Expected file '%s' not found; falling back to most recent file: %s",
            candidate.name, recent,
        )
        return recent

    log.error("Could not locate downloaded file for URL: %s", url)
    return None


def process_download(filepath: Path, config: dict) -> str:
    """Apply post-download rules. Returns a human-readable note."""
    if not config.get("auto_unzip"):
        return ""
    if filepath.suffix.lower() != ".zip":
        return ""

    extract_dir = filepath.parent
    log.info("Unzipping %s -> %s", filepath, extract_dir)
    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        log.error("Bad zip file: %s", filepath)
        return "Warning: file does not appear to be a valid zip."

    if config.get("delete_after_unzip"):
        filepath.unlink()
        log.info("Deleted archive after unzip: %s", filepath)
        return f"Unzipped and removed archive -> {extract_dir}"

    return f"Unzipped -> {extract_dir}"


class DownloadManager:
    """
    Manages a single background wget download.
    The worker thread must never call any pygame functions.
    """

    def __init__(self):
        self._thread: "threading.Thread | None" = None
        self._result: "tuple | None" = None   # (filepath | None, effective_cfg)
        self.url: str = ""
        self.active: bool = False
        self._spinner_frame: int = 0

    def start(self, url: str, dest_dir: str, effective_cfg: dict):
        """Kick off the download in a daemon thread."""
        self.url = url
        self.active = True
        self._result = None
        self._spinner_frame = 0
        log.info("DownloadManager starting thread for: %s", url)
        self._thread = threading.Thread(
            target=self._worker,
            args=(url, dest_dir, effective_cfg),
            daemon=True,
        )
        self._thread.start()

    def _worker(self, url: str, dest_dir: str, effective_cfg: dict):
        filepath = download_file(url, dest_dir)
        self._result = (filepath, effective_cfg)

    def poll(self) -> "tuple[bool, str]":
        """
        Call once per frame while active is True.
        Returns (just_finished, spinner_status_text).
        When just_finished is True, read .result to get the outcome.
        """
        if not self.active:
            return False, ""

        self._spinner_frame = (self._spinner_frame + 1) % len(SPINNER)
        spin = SPINNER[self._spinner_frame]
        status = f"{spin}  Downloading  {self.url} ..."

        if self._thread and not self._thread.is_alive():
            self.active = False
            return True, status

        return False, status

    @property
    def result(self) -> "tuple | None":
        """(filepath | None, effective_cfg) — available once active is False."""
        return self._result
