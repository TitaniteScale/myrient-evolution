from pathlib import Path

# Display
SCREEN_WIDTH = 0   # 0 = native resolution in fullscreen
SCREEN_HEIGHT = 0
FPS = 30

# Colors
BG_COLOR            = (20,  20,  30)
TEXT_COLOR          = (220, 220, 220)
DIM_COLOR           = (110, 110, 130)
HIGHLIGHT_BG        = (55,  80,  150)
HIGHLIGHT_TEXT      = (255, 255, 255)
SCROLLBAR_BG        = (50,  50,  70)
SCROLLBAR_FG        = (140, 140, 200)
STATUS_OK           = (100, 210, 120)
STATUS_ERR          = (210, 90,  80)
STATUS_INFO         = (180, 180, 100)
SEARCH_BG           = (35,  35,  55)
SEARCH_BORDER       = (100, 110, 180)
SEARCH_TEXT         = (230, 230, 255)
VKB_BG              = (28,  28,  45)
VKB_KEY_NORMAL      = (60,  62,  90)
VKB_KEY_HOVER       = (90,  110, 200)
VKB_KEY_SPECIAL     = (50,  80,  70)
VKB_KEY_SPECIAL_HOVER = (70, 160, 120)
VKB_KEY_TEXT        = (220, 220, 255)
VKB_BORDER          = (80,  90,  160)

# Typography / layout
FONT_SIZE   = 22
HEADER_SIZE = 28
STATUS_SIZE = 18
ITEM_HEIGHT = 34
PADDING     = 20

# Controller button indices (Xbox layout)
BTN_A      = 0
BTN_B      = 1
BTN_X      = 2
BTN_Y      = 3   # open search / virtual keyboard
BTN_SELECT = 6
BTN_START  = 7

AXIS_LEFT_X          = 0
AXIS_LEFT_Y          = 1
AXIS_STICK_THRESHOLD = 0.5

# Virtual keyboard
VKB_ROWS = [
    ["Q","W","E","R","T","Y","U","I","O","P"],
    ["A","S","D","F","G","H","J","K","L"],
    ["Z","X","C","V","B","N","M"],
    ["SPACE","BACK","CLEAR","DONE"],
]
VKB_KEY_W   = 74
VKB_KEY_H   = 54
VKB_KEY_PAD = 6

# Download spinner (braille dots)
SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

# Config defaults
DEFAULT_CONFIG = {
    "urls":              [],
    "download_dir":      str(Path.home() / "Downloads"),
    "link_selector":     "a[href] attr{href}",
    "auto_unzip":        False,
    "delete_after_unzip": False,
}

CONFIG_PATH = Path(__file__).parent / "config.json"

# Screen names
SCREEN_URL_SELECT  = "url_select"
SCREEN_LINK_BROWSE = "link_browse"
