import pygame
import pygame.freetype

from config import parse_url_entries, resolve_config
from constants import (
    AXIS_LEFT_X,
    AXIS_LEFT_Y,
    AXIS_STICK_THRESHOLD,
    BTN_A,
    BTN_B,
    BTN_SELECT,
    BTN_START,
    BTN_Y,
    DEFAULT_CONFIG,
    FONT_SIZE,
    FPS,
    HEADER_SIZE,
    ITEM_HEIGHT,
    PADDING,
    SCREEN_HEIGHT,
    SCREEN_LINK_BROWSE,
    SCREEN_URL_SELECT,
    SCREEN_WIDTH,
    STATUS_ERR,
    STATUS_INFO,
    STATUS_OK,
    STATUS_SIZE,
)
from downloader import DownloadManager, process_download
from fetcher import fetch_links
from renderer import Renderer
from vkb import VirtualKeyboard


class HappyCrush(Renderer):
    def __init__(self, config: dict):
        self.config = config
        self.url_entries = parse_url_entries(config.get("urls", []))

        pygame.init()
        pygame.joystick.init()

        self.screen = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN
        )
        pygame.display.set_caption("Happy Crush")
        self.width = self.screen.get_width()
        self.height = self.screen.get_height()

        self.font = pygame.freetype.SysFont("monospace", FONT_SIZE)
        self.header_font = pygame.freetype.SysFont("monospace", HEADER_SIZE, bold=True)
        self.small_font = pygame.freetype.SysFont("monospace", STATUS_SIZE)
        self.vkb_font = pygame.freetype.SysFont("monospace", 18, bold=True)

        self.joystick = None
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()

        self.clock = pygame.time.Clock()

        self._header_bottom = HEADER_SIZE + PADDING * 3
        self._footer_top = self.height - (STATUS_SIZE * 2 + PADDING * 3)
        self.visible_rows = (self._footer_top - self._header_bottom) // ITEM_HEIGHT

        # Analog stick debounce — separate per axis
        self._axis_y_held = False
        self._axis_x_held = False

        # URL picker state
        self.url_cursor = 0
        self.url_scroll_offset = 0

        # Link browser state
        self.active_entry = None
        self.links = []
        self.link_cursor = 0
        self.link_scroll_offset = 0

        # Search state
        self.search_mode = False
        self.search_query = ""
        self._filtered_links = []
        self.search_cursor = 0
        self.search_scroll_offset = 0

        # Virtual keyboard
        self.vkb = VirtualKeyboard()

        # Download manager
        self.dm = DownloadManager()

        # Status bar
        self.status_text = ""
        self.status_color = STATUS_INFO

        if len(self.url_entries) == 1:
            self._open_url(self.url_entries[0])
            self.current_screen = SCREEN_LINK_BROWSE
        elif len(self.url_entries) == 0:
            self._set_status(
                "No URLs configured -- add entries to urls in config.json",
                STATUS_ERR,
            )
            self.current_screen = SCREEN_URL_SELECT
        else:
            self._set_status("Choose a source.", STATUS_INFO)
            self.current_screen = SCREEN_URL_SELECT

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _set_status(self, msg: str, color: tuple = STATUS_INFO):
        self.status_text = msg
        self.status_color = color

    # ------------------------------------------------------------------
    # URL picker helpers
    # ------------------------------------------------------------------

    def _move_url_cursor(self, direction: int):
        if not self.url_entries:
            return
        self.url_cursor = max(
            0, min(len(self.url_entries) - 1, self.url_cursor + direction)
        )
        if self.url_cursor < self.url_scroll_offset:
            self.url_scroll_offset = self.url_cursor
        elif self.url_cursor >= self.url_scroll_offset + self.visible_rows:
            self.url_scroll_offset = self.url_cursor - self.visible_rows + 1

    def _select_url(self):
        if not self.url_entries:
            return
        self._open_url(self.url_entries[self.url_cursor])
        self.current_screen = SCREEN_LINK_BROWSE

    def _open_url(self, entry: dict):
        self.active_entry = entry
        self.links = []
        self.link_cursor = 0
        self.link_scroll_offset = 0
        self._load_links()

    # ------------------------------------------------------------------
    # Link browser helpers
    # ------------------------------------------------------------------

    def _load_links(self):
        if not self.active_entry:
            return
        url = self.active_entry["url"]
        self._set_status(f"Fetching  {url} ...", STATUS_INFO)
        self._render()
        pygame.display.flip()

        selector = self.config.get("link_selector", DEFAULT_CONFIG["link_selector"])
        self.links = fetch_links(url, selector)
        self.link_cursor = 0
        self.link_scroll_offset = 0

        if self.links:
            self._set_status(
                f"{len(self.links)} links found.  Navigate with D-pad, download with A.",
                STATUS_OK,
            )
        else:
            self._set_status(
                "No links found. Check the URL and link_selector in config.json.",
                STATUS_ERR,
            )

    def _move_link_cursor(self, direction: int):
        items = self._active_links()
        if not items:
            return
        if self.search_mode:
            rows = self._search_visible_rows()
            self.search_cursor = max(
                0, min(len(items) - 1, self.search_cursor + direction)
            )
            if self.search_cursor < self.search_scroll_offset:
                self.search_scroll_offset = self.search_cursor
            elif self.search_cursor >= self.search_scroll_offset + rows:
                self.search_scroll_offset = self.search_cursor - rows + 1
        else:
            self.link_cursor = max(0, min(len(items) - 1, self.link_cursor + direction))
            if self.link_cursor < self.link_scroll_offset:
                self.link_scroll_offset = self.link_cursor
            elif self.link_cursor >= self.link_scroll_offset + self.visible_rows:
                self.link_scroll_offset = self.link_cursor - self.visible_rows + 1

    # ------------------------------------------------------------------
    # Download (non-blocking)
    # ------------------------------------------------------------------

    def _download_selected(self):
        if self.dm.active:
            return
        items = self._active_links()
        cursor = self.search_cursor if self.search_mode else self.link_cursor
        if not items or cursor >= len(items):
            return

        url = items[cursor]
        effective = resolve_config(self.config, self.active_entry or {})
        dest_dir = effective.get("download_dir", DEFAULT_CONFIG["download_dir"])

        self._set_status(f"Starting download: {url}", STATUS_INFO)
        self.dm.start(url, dest_dir, effective)

    def _check_download(self):
        """Poll the DownloadManager each frame; finalise on completion."""
        if not self.dm.active:
            return

        finished, status_text = self.dm.poll()
        self._set_status(status_text, STATUS_INFO)

        if finished:
            # Exit search mode so the user lands straight back on the list.
            if self.search_mode:
                self._exit_search()

            # Drain only events that were queued *before* this moment so that
            # a button pressed after the download finishes is not swallowed.
            cutoff = pygame.time.get_ticks()
            pygame.event.pump()
            pygame.event.get()  # pull everything — we already exited search above

            result = self.dm.result
            if result is None or result[0] is None:
                self._set_status(f"Download failed for  {self.dm.url}", STATUS_ERR)
                return

            filepath, effective = result
            note = process_download(filepath, effective)
            base_msg = f"Saved -> {filepath}"
            self._set_status(f"{base_msg}   {note}".strip(), STATUS_OK)
            # Control is now fully restored to normal gamepad navigation.

    # ------------------------------------------------------------------
    # Search helpers
    # ------------------------------------------------------------------

    def _active_links(self) -> list:
        if self.search_mode and self.search_query:
            return self._filtered_links
        return self.links

    def _enter_search(self, use_vkb: bool = False):
        self.search_mode = True
        self.search_query = ""
        self._filtered_links = self.links[:]
        self.search_cursor = 0
        self.search_scroll_offset = 0
        if use_vkb:
            self.vkb.open()
            self._set_status(
                "D-pad = navigate keys  |  A = type  |  DONE / B = close keyboard",
                STATUS_INFO,
            )
        else:
            self._set_status("Type to search  |  Esc / B to close", STATUS_INFO)

    def _exit_search(self):
        self.search_mode = False
        self.search_query = ""
        self._filtered_links = []
        self.vkb.close()
        n = len(self.links)
        self._set_status(
            f"{n} links.  Navigate with D-pad, download with A.",
            STATUS_OK if n else STATUS_ERR,
        )

    def _update_search_filter(self):
        q = self.search_query.lower()
        self._filtered_links = (
            [link for link in self.links if q in link.lower()] if q else self.links[:]
        )
        self.search_cursor = 0
        self.search_scroll_offset = 0

    def _search_visible_rows(self) -> int:
        search_box_h = ITEM_HEIGHT + 6
        extra = self.vkb.panel_height + 6 if self.vkb.active else 0
        return max(
            0,
            (self._footer_top - self._header_bottom - search_box_h - extra)
            // ITEM_HEIGHT,
        )

    def _apply_vkb_action(self, action: str):
        """Apply an action string returned by VirtualKeyboard.activate()."""
        if action == "done":
            n = len(self._active_links())
            self._set_status(
                f"{n} match(es)  |  D-pad = scroll  |  A = download  |  Y = reopen keyboard  |  B = close search",
                STATUS_INFO,
            )
        elif action == "back":
            if self.search_query:
                self.search_query = self.search_query[:-1]
                self._update_search_filter()
            # if query already empty, keep keyboard open
        elif action == "clear":
            self.search_query = ""
            self._update_search_filter()
        elif action == "space":
            self.search_query += " "
            self._update_search_filter()
        elif action.startswith("char:"):
            self.search_query += action[5:]
            self._update_search_filter()

    def _back_to_url_select(self):
        self.search_mode = False
        self.search_query = ""
        self.vkb.close()
        self.current_screen = SCREEN_URL_SELECT
        self._set_status("Choose a source.", STATUS_INFO)

    # ------------------------------------------------------------------
    # Input: keyboard
    # ------------------------------------------------------------------

    def _handle_key(self, event) -> bool:
        key = event.key

        if self.current_screen == SCREEN_URL_SELECT:
            if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return False
            elif key == pygame.K_UP:
                self._move_url_cursor(-1)
            elif key == pygame.K_DOWN:
                self._move_url_cursor(1)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._select_url()

        else:  # SCREEN_LINK_BROWSE
            if self.search_mode:
                if self.vkb.active:
                    # Physical keyboard still works even when VKB is showing
                    if key == pygame.K_ESCAPE:
                        self.vkb.close()
                        self._set_status(
                            "Type to search  |  Esc / B to close", STATUS_INFO
                        )
                    elif key == pygame.K_BACKSPACE:
                        self._apply_vkb_action("back")
                    elif event.unicode and event.unicode.isprintable():
                        self.search_query += event.unicode.upper()
                        self._update_search_filter()
                else:
                    if key == pygame.K_ESCAPE:
                        self._exit_search()
                    elif key == pygame.K_BACKSPACE:
                        if self.search_query:
                            self.search_query = self.search_query[:-1]
                            self._update_search_filter()
                        else:
                            self._exit_search()
                    elif key == pygame.K_UP:
                        self._move_link_cursor(-1)
                    elif key == pygame.K_DOWN:
                        self._move_link_cursor(1)
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._download_selected()
                    elif event.unicode and event.unicode.isprintable():
                        self.search_query += event.unicode
                        self._update_search_filter()
            else:
                if key == pygame.K_ESCAPE:
                    return False
                elif key == pygame.K_UP:
                    self._move_link_cursor(-1)
                elif key == pygame.K_DOWN:
                    self._move_link_cursor(1)
                elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self._download_selected()
                elif key == pygame.K_r:
                    self._load_links()
                elif key in (pygame.K_SLASH, pygame.K_KP_DIVIDE):
                    self._enter_search(use_vkb=False)
                elif key == pygame.K_BACKSPACE:
                    self._back_to_url_select()

        return True

    # ------------------------------------------------------------------
    # Input: gamepad buttons
    # ------------------------------------------------------------------

    def _handle_button(self, button: int) -> bool:
        # Always allow quitting; block everything else during a download
        if button == BTN_START:
            return False
        if self.dm.active:
            return True

        if self.current_screen == SCREEN_URL_SELECT:
            if button == BTN_A:
                self._select_url()
            elif button == BTN_B:
                return False  # quit from the top-level screen

        else:  # SCREEN_LINK_BROWSE
            if self.vkb.active:
                if button == BTN_A:
                    self._apply_vkb_action(self.vkb.activate())
                elif button == BTN_B:
                    self.vkb.close()
                    n = len(self._active_links())
                    self._set_status(
                        f"{n} match(es)  |  D-pad = scroll  |  A = download  |  Y = reopen keyboard  |  B = close search",
                        STATUS_INFO,
                    )
            elif self.search_mode:
                if button == BTN_A:
                    self._download_selected()
                elif button == BTN_B:
                    self._exit_search()
                elif button == BTN_Y:
                    self.vkb.open()
                    self._set_status(
                        "D-pad = navigate keys  |  A = type  |  DONE / B = close keyboard",
                        STATUS_INFO,
                    )
            else:
                if button == BTN_A:
                    self._download_selected()
                elif button == BTN_B:
                    if len(self.url_entries) <= 1:
                        return False  # only one URL, nowhere to go back — quit
                    self._back_to_url_select()
                elif button == BTN_Y:
                    self._enter_search(use_vkb=True)
                elif button == BTN_SELECT:
                    self._load_links()

        return True

    # ------------------------------------------------------------------
    # Input: D-pad hat
    # ------------------------------------------------------------------

    def _handle_hat(self, value):
        x, y = value

        if self.vkb.active:
            if y == 1:
                self.vkb.move(-1, 0)
            elif y == -1:
                self.vkb.move(1, 0)
            if x == -1:
                self.vkb.move(0, -1)
            elif x == 1:
                self.vkb.move(0, 1)
            return

        direction = -1 if y == 1 else (1 if y == -1 else 0)
        if direction != 0:
            if self.current_screen == SCREEN_URL_SELECT:
                self._move_url_cursor(direction)
            else:
                self._move_link_cursor(direction)

    # ------------------------------------------------------------------
    # Input: analog stick (polled every frame)
    # ------------------------------------------------------------------

    def _handle_axis(self):
        if not self.joystick:
            return

        axis_y = self.joystick.get_axis(AXIS_LEFT_Y)
        if abs(axis_y) > AXIS_STICK_THRESHOLD:
            if not self._axis_y_held:
                direction = 1 if axis_y > 0 else -1
                if self.vkb.active:
                    self.vkb.move(direction, 0)
                elif self.current_screen == SCREEN_URL_SELECT:
                    self._move_url_cursor(direction)
                else:
                    self._move_link_cursor(direction)
                self._axis_y_held = True
        else:
            self._axis_y_held = False

        axis_x = self.joystick.get_axis(AXIS_LEFT_X)
        if abs(axis_x) > AXIS_STICK_THRESHOLD:
            if not self._axis_x_held and self.vkb.active:
                direction = 1 if axis_x > 0 else -1
                self.vkb.move(0, direction)
                self._axis_x_held = True
        else:
            self._axis_x_held = False

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self._handle_key(event)
                elif event.type == pygame.JOYBUTTONDOWN:
                    running = self._handle_button(event.button)
                elif event.type == pygame.JOYHATMOTION:
                    self._handle_hat(event.value)

            self._handle_axis()
            self._check_download()
            self._render()
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()
