"""
Renderer mixin for HappyCrush.

Provides all _render_* methods. Mixed into HappyCrush (app.py).
Expected attributes on self (provided by HappyCrush.__init__):
  screen, width, height
  font, header_font, small_font, vkb_font
  current_screen, url_entries, url_cursor, url_scroll_offset
  links, link_cursor, link_scroll_offset
  search_mode, search_query
  search_cursor, search_scroll_offset
  vkb  (VirtualKeyboard instance)
  status_text, status_color
  _header_bottom, _footer_top, visible_rows
  active_entry
  _active_links(), _search_visible_rows()
"""

from urllib.parse import unquote

import pygame
import pygame.freetype

from constants import (
    BG_COLOR,
    DIM_COLOR,
    FONT_SIZE,
    HEADER_SIZE,
    HIGHLIGHT_BG,
    HIGHLIGHT_TEXT,
    ITEM_HEIGHT,
    PADDING,
    SCREEN_URL_SELECT,
    SCROLLBAR_BG,
    SCROLLBAR_FG,
    SEARCH_BG,
    SEARCH_BORDER,
    SEARCH_TEXT,
    STATUS_SIZE,
    TEXT_COLOR,
)


class Renderer:
    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _truncate(self, text: str, max_px: int) -> str:
        if self.font.get_rect(text).width <= max_px:
            return text
        while text and self.font.get_rect("..." + text).width > max_px:
            text = text[1:]
        return "..." + text

    def _render_list(
        self,
        items: list,
        cursor: int,
        scroll_offset: int,
        label_fn=None,
        top_y: "int | None" = None,
        max_rows: "int | None" = None,
    ):
        if label_fn is None:
            label_fn = str
        if top_y is None:
            top_y = self._header_bottom
        if max_rows is None:
            max_rows = self.visible_rows

        list_max_w = self.width - PADDING * 3 - 10

        for row, item in enumerate(items[scroll_offset : scroll_offset + max_rows]):
            abs_idx = scroll_offset + row
            selected = abs_idx == cursor
            item_y = top_y + row * ITEM_HEIGHT

            if selected:
                rect = pygame.Rect(
                    PADDING,
                    item_y,
                    self.width - PADDING * 2 - 10,
                    ITEM_HEIGHT - 2,
                )
                pygame.draw.rect(self.screen, HIGHLIGHT_BG, rect, border_radius=4)
                color = HIGHLIGHT_TEXT
            else:
                color = TEXT_COLOR

            display = self._truncate(label_fn(item), list_max_w)
            self.font.render_to(
                self.screen,
                (PADDING + 6, item_y + (ITEM_HEIGHT - FONT_SIZE) // 2),
                display,
                color,
            )

        if not items:
            self.font.render_to(
                self.screen,
                (PADDING, top_y + PADDING),
                "-- nothing here --",
                DIM_COLOR,
            )

        # Scrollbar
        if len(items) > max_rows:
            sb_x = self.width - PADDING - 6
            sb_top = top_y
            sb_height = self._footer_top - sb_top
            pygame.draw.rect(
                self.screen,
                SCROLLBAR_BG,
                pygame.Rect(sb_x, sb_top, 6, sb_height),
                border_radius=3,
            )
            thumb_h = max(20, sb_height * max_rows // len(items))
            thumb_y = sb_top + sb_height * scroll_offset // len(items)
            pygame.draw.rect(
                self.screen,
                SCROLLBAR_FG,
                pygame.Rect(sb_x, thumb_y, 6, thumb_h),
                border_radius=3,
            )

    def _render_chrome(self, title: str, controls_hint: str):
        self.screen.fill(BG_COLOR)

        self.header_font.render_to(self.screen, (PADDING, PADDING), title, TEXT_COLOR)

        sep_y = self._header_bottom - PADDING
        pygame.draw.line(
            self.screen,
            DIM_COLOR,
            (PADDING, sep_y),
            (self.width - PADDING, sep_y),
            1,
        )
        pygame.draw.line(
            self.screen,
            DIM_COLOR,
            (PADDING, self._footer_top),
            (self.width - PADDING, self._footer_top),
            1,
        )

        self.small_font.render_to(
            self.screen,
            (PADDING, self._footer_top + 6),
            controls_hint,
            DIM_COLOR,
        )
        self.small_font.render_to(
            self.screen,
            (PADDING, self._footer_top + STATUS_SIZE + 12),
            self.status_text,
            self.status_color,
        )

    # ------------------------------------------------------------------
    # URL picker screen
    # ------------------------------------------------------------------

    def _render_url_select(self):
        self._render_chrome(
            title="Myrient: Evolution  --  Select a source",
            controls_hint=(
                "Up/Down: D-pad or Left Stick     "
                "Select: A / Enter     "
                "Quit: Start / Esc"
            ),
        )
        self._render_list(
            items=self.url_entries,
            cursor=self.url_cursor,
            scroll_offset=self.url_scroll_offset,
            label_fn=lambda e: e["name"],
        )

    # ------------------------------------------------------------------
    # Link browser screen
    # ------------------------------------------------------------------

    def _render_search_box(self) -> int:
        """Draw the search input box. Returns the y coordinate below it."""
        box_y = self._header_bottom
        box_h = ITEM_HEIGHT + 2
        box_rect = pygame.Rect(PADDING, box_y, self.width - PADDING * 2 - 10, box_h)
        pygame.draw.rect(self.screen, SEARCH_BG, box_rect, border_radius=4)
        pygame.draw.rect(self.screen, SEARCH_BORDER, box_rect, width=1, border_radius=4)

        # Block cursor when the VKB is open, underline cursor for keyboard typing
        cursor_char = "|" if self.vkb.active else "_"
        query_display = "/ " + self.search_query + cursor_char
        self.font.render_to(
            self.screen,
            (PADDING + 8, box_y + (box_h - FONT_SIZE) // 2),
            query_display,
            SEARCH_TEXT,
        )

        n = len(self._active_links())
        count_text = f"{n} match{'es' if n != 1 else ''}"
        count_surf, _ = self.small_font.render(count_text, DIM_COLOR)
        self.screen.blit(
            count_surf,
            (
                self.width - PADDING * 2 - 10 - count_surf.get_width(),
                box_y + (box_h - STATUS_SIZE) // 2,
            ),
        )
        return box_y + box_h + 4

    def _render_link_browse(self):
        name = self.active_entry["name"] if self.active_entry else ""

        if self.search_mode:
            if self.vkb.active:
                hint = (
                    "D-pad = navigate keys  |  A = type  |  DONE / B = close keyboard"
                )
            else:
                hint = "Up/Down = scroll  |  A = download  |  Y = keyboard  |  B = close search"
        else:
            hint = (
                "Up/Down: D-pad or Stick     Download: A     "
                "Search: Y     Refresh: Select     Back: B     Quit: Start/Esc"
            )

        self._render_chrome(title=f"happy-crush  --  {name}", controls_hint=hint)

        if self.search_mode:
            list_top = self._render_search_box()
            if self.vkb.active:
                list_top = self.vkb.render(
                    self.screen, self.vkb_font, list_top, self.width
                )
            self._render_list(
                items=self._active_links(),
                cursor=self.search_cursor,
                scroll_offset=self.search_scroll_offset,
                top_y=list_top,
                max_rows=self._search_visible_rows(),
                label_fn=lambda url: unquote(url.rstrip("/").split("/")[-1]),
            )
        else:
            self._render_list(
                items=self.links,
                cursor=self.link_cursor,
                scroll_offset=self.link_scroll_offset,
                label_fn=lambda url: unquote(url.rstrip("/").split("/")[-1]),
            )

    # ------------------------------------------------------------------
    # Top-level render dispatch
    # ------------------------------------------------------------------

    def _render(self):
        if self.current_screen == SCREEN_URL_SELECT:
            self._render_url_select()
        else:
            self._render_link_browse()
