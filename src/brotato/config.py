"""Configuration constants, arena dimensions, and tier styling."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
ASSETS_DIR = ROOT_DIR / "assets"

# Display & Timing
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
TARGET_FPS = 60
FIXED_DT = 1.0 / 60.0

# Arena World Bounds (faithful to Brotato's enclosed arena)
ARENA_WIDTH = 1600.0
ARENA_HEIGHT = 1200.0
ARENA_WALL_MARGIN = 44.0
SPATIAL_CELL_SIZE = 96.0

# Player Base Constants
PLAYER_BASE_SPEED = 325.0
PLAYER_RADIUS = 20.0
PLAYER_BASE_PICKUP_RADIUS = 95.0
PLAYER_INVULN_DURATION = 0.45
BASE_CONSUMABLE_HEAL = 3
DEFAULT_DODGE_CAP = 60.0
MAX_LIFESTEAL_PER_SEC = 10

# Visual & Tier Palette
TIER_NAMES = {
    1: "Common",
    2: "Uncommon",
    3: "Rare",
    4: "Legendary",
}

TIER_ROMAN = {
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
}

TIER_COLORS = {
    1: (170, 176, 186),   # Tier I - Grey/Silver
    2: (82, 165, 255),    # Tier II - Blue
    3: (186, 104, 245),   # Tier III - Purple
    4: (255, 78, 78),     # Tier IV - Crimson Red
}

TIER_BG_COLORS = {
    1: (44, 47, 56),
    2: (30, 52, 78),
    3: (58, 36, 78),
    4: (78, 30, 34),
}

# Colors
COLOR_BG = (22, 23, 28)
COLOR_ARENA_FLOOR_A = (40, 42, 48)
COLOR_ARENA_FLOOR_B = (45, 47, 54)
COLOR_ARENA_WALL = (24, 25, 30)
COLOR_ARENA_BORDER = (88, 78, 70)

COLOR_MATERIAL = (75, 236, 115)
COLOR_MATERIAL_DARK = (38, 160, 68)
COLOR_CONSUMABLE = (115, 245, 95)
COLOR_CRATE = (245, 195, 72)

COLOR_HP = (218, 58, 66)
COLOR_HP_BG = (48, 22, 26)
COLOR_XP = (84, 210, 120)
COLOR_XP_BG = (24, 48, 34)

COLOR_WHITE = (242, 244, 248)
COLOR_MUTED = (162, 168, 180)
COLOR_GOOD = (102, 230, 122)
COLOR_BAD = (242, 92, 92)
COLOR_GOLD = (255, 214, 86)
