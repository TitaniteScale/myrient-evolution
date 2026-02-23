import pygame
import pygame.freetype

from constants import (
    VKB_ROWS, VKB_KEY_W, VKB_KEY_H, VKB_KEY_PAD,
    VKB_BG, VKB_KEY_NORMAL, VKB_KEY_HOVER,
    VKB_KEY_SPECIAL, VKB_KEY_SPECIAL_HOVER,
    VKB_KEY_TEXT, VKB_BORDER,
)


class VirtualKeyboard:
    """
    Self-contained on-screen keyboard for gamepad input.

    Usage
    -----
    - Call open() to show it, close() to hide it.
    - Call move(d_row, d_col) in response to D-pad / stick events.
    - Call activate() to press the highlighted key; it returns a string
      action that the caller applies to the search query:
        "char:<X>"  append character X
        "space"     append a space
        "back"      delete last character
        "clear"     clear the query
        "done"      close the keyboard (open=False set automatically)
    - Call render(screen, font, top_y, screen_w) each frame when active.
      It returns the y coordinate immediately below the drawn panel.
    """

    def __init__(self):
        self.active = False
        self.row = 0
        self.col = 0
        self._geom = self._build_geometry()

    # ------------------------------------------------------------------
    # Geometry (built once)
    # ------------------------------------------------------------------

    def _build_geometry(self) -> dict:
        max_keys = max(len(row) for row in VKB_ROWS)
        total_w   = max_keys * (VKB_KEY_W + VKB_KEY_PAD) - VKB_KEY_PAD
        panel_pad = 16
        panel_w   = total_w + panel_pad * 2

        geom: dict = {
            "panel_w":   panel_w,
            "panel_pad": panel_pad,
            "total_w":   total_w,
        }

        for row_idx, row in enumerate(VKB_ROWS):
            n     = len(row)
            row_y = row_idx * (VKB_KEY_H + VKB_KEY_PAD)

            if row_idx == len(VKB_ROWS) - 1:
                # Special-action row: spread keys evenly across full width
                special_w = (total_w - (n - 1) * VKB_KEY_PAD) // n
                for col_idx in range(n):
                    x = col_idx * (special_w + VKB_KEY_PAD)
                    geom[(row_idx, col_idx)] = pygame.Rect(
                        x, row_y, special_w, VKB_KEY_H
                    )
            else:
                # Letter rows: centre within the total keyboard width
                row_w    = n * (VKB_KEY_W + VKB_KEY_PAD) - VKB_KEY_PAD
                x_offset = (total_w - row_w) // 2
                for col_idx in range(n):
                    x = x_offset + col_idx * (VKB_KEY_W + VKB_KEY_PAD)
                    geom[(row_idx, col_idx)] = pygame.Rect(
                        x, row_y, VKB_KEY_W, VKB_KEY_H
                    )

        total_h = len(VKB_ROWS) * (VKB_KEY_H + VKB_KEY_PAD) - VKB_KEY_PAD
        geom["total_h"] = total_h
        geom["panel_h"] = total_h + panel_pad * 2
        return geom

    @property
    def panel_height(self) -> int:
        return self._geom["panel_h"]

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def open(self):
        self.active = True
        self.row = 0
        self.col = 0

    def close(self):
        self.active = False

    def move(self, d_row: int, d_col: int):
        """Move the cursor. When changing rows, preserve proportional position."""
        new_row = (self.row + d_row) % len(VKB_ROWS)
        new_col = self.col

        if d_row != 0:
            old_len = len(VKB_ROWS[self.row])
            new_len = len(VKB_ROWS[new_row])
            new_col = round(new_col / max(old_len - 1, 1) * max(new_len - 1, 1))

        new_col = max(0, min(len(VKB_ROWS[new_row]) - 1, new_col + d_col))
        self.row = new_row
        self.col = new_col

    def activate(self) -> str:
        """
        Press the highlighted key and return the action string.
        Also calls close() automatically when the DONE key is pressed.
        """
        key = VKB_ROWS[self.row][self.col]
        if key == "DONE":
            self.close()
            return "done"
        if key == "BACK":
            return "back"
        if key == "CLEAR":
            return "clear"
        if key == "SPACE":
            return "space"
        return f"char:{key}"

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(
        self,
        screen: pygame.Surface,
        font: "pygame.freetype.Font",
        top_y: int,
        screen_w: int,
    ) -> int:
        """Draw the keyboard panel and return the y coordinate below it."""
        g         = self._geom
        panel_w   = g["panel_w"]
        panel_h   = g["panel_h"]
        panel_pad = g["panel_pad"]
        panel_x   = (screen_w - panel_w) // 2

        panel_rect = pygame.Rect(panel_x, top_y, panel_w, panel_h)
        pygame.draw.rect(screen, VKB_BG,     panel_rect, border_radius=8)
        pygame.draw.rect(screen, VKB_BORDER, panel_rect, width=1, border_radius=8)

        origin_x     = panel_x + panel_pad
        origin_y     = top_y   + panel_pad
        special_row  = len(VKB_ROWS) - 1

        for row_idx, row in enumerate(VKB_ROWS):
            is_special = row_idx == special_row
            for col_idx, label in enumerate(row):
                rel      = g[(row_idx, col_idx)]
                key_rect = pygame.Rect(
                    origin_x + rel.x,
                    origin_y + rel.y,
                    rel.width,
                    rel.height,
                )
                selected = (row_idx == self.row and col_idx == self.col)

                if selected:
                    bg = VKB_KEY_SPECIAL_HOVER if is_special else VKB_KEY_HOVER
                else:
                    bg = VKB_KEY_SPECIAL if is_special else VKB_KEY_NORMAL

                pygame.draw.rect(screen, bg, key_rect, border_radius=6)
                if selected:
                    pygame.draw.rect(screen, VKB_BORDER, key_rect, width=2, border_radius=6)

                display_label = "SPC" if label == "SPACE" else label
                text_surf, text_rect = font.render(display_label, VKB_KEY_TEXT)
                tx = key_rect.x + (key_rect.width  - text_rect.width)  // 2
                ty = key_rect.y + (key_rect.height - text_rect.height) // 2
                screen.blit(text_surf, (tx, ty))

        return top_y + panel_h + 6
