# ===== Cấu hình cá & tỉ lệ =====
FISH_POOLS = {
    "trash": [
        {"name": "Giày rách", "emoji": "👢", "rate": 1, "base_weight": 0.5, "price_per_kg": 10},
        {"name": "Vỏ lon", "emoji": "🥫", "rate": 1, "base_weight": 0.2, "price_per_kg": 30},
        {"name": "Xương cá", "emoji": "🦴", "rate": 1, "base_weight": 0.1, "price_per_kg": 20},
    ],
    "common": [
        {"name": "Cá rô", "emoji": "<:CaRo:1468165132151423098>", "rate": 1, "base_weight": 3, "price_per_kg": 10},
        {"name": "Cá trắm", "emoji": "<:CaTram:1468165172316078100>", "rate": 1, "base_weight": 2, "price_per_kg": 14},
        {"name": "Cá mè", "emoji": "<:CaMe:1467811756876496978>", "rate": 1, "base_weight": 2.5, "price_per_kg": 15,}
    ],
    "uncommon": [
        {"name": "Cá hồi", "emoji": "<:CaHoi:1468165254612652106>", "rate": 1, "base_weight": 4, "price_per_kg": 25},
        {"name": "Cá ngừ", "emoji": "🐠", "rate": 1, "base_weight": 3, "price_per_kg": 30},
    ],
    "rare": [
        {"name": "Cá kiếm", "emoji": "<:CaKiem:1468165272656674896>", "rate": 1, "base_weight": 6, "price_per_kg": 120},
        {"name": "Cá vược khổng lồ", "emoji": "<:CaVuoc:1468165192423837861>", "rate": 0.8, "base_weight": 12, "price_per_kg": 80},
    ],
    "epic": [
        {"name": "Cánh cụt", "emoji": "<:CanhCut:1467792554241036380>", "rate": 1, "base_weight": 6, "price_per_kg": 2000},
        {"name": "Mực", "emoji": "<:Muc:1468165213890154602>", "rate": 1, "base_weight": 3, "price_per_kg": 3500},
        {"name": "Cá heo", "emoji": "🐬", "rate": 0.7, "base_weight": 30, "price_per_kg": 500},
    ],
    "legendary": [
        {"name": "Cá voi xanh", "emoji": "🐋", "rate": 1, "base_weight": 500, "price_per_kg": 200},
    ],
    "mythical": [
        {"name": "Cá thần", "emoji": "🐟✨", "rate": 1, "base_weight": 100, "price_per_kg": 3000},
    ],
    "unreal": [
        {"name": "Cá mập trắng khổng lồ", "emoji": "🦈👑", "rate": 1, "base_weight": 1500, "price_per_kg": 5000},
    ],
}

# Cấu hình thuật toán câu cá mới (Weighted Random + Luck)
FISHING_CONFIG = {
    "trash":     {"base_weight": 10000, "luck_factor": 0.0},
    "common":    {"base_weight": 50000,  "luck_factor": 0.05},
    "uncommon":  {"base_weight": 25000,  "luck_factor": 0.5},
    "rare":      {"base_weight": 10000,  "luck_factor": 1.0},
    "epic":      {"base_weight": 5000,   "luck_factor": 2.0},
    "legendary": {"base_weight": 1000,   "luck_factor": 5.0},
    "mythical":  {"base_weight": 100,    "luck_factor": 15.0}, # Tương ứng GODLY
    "unreal":    {"base_weight": 1,     "luck_factor": 50.0}, # Giữ lại Unreal cho game
}

RARITY_DISPLAY = {"trash": "Trash", "common": "Common", "uncommon": "Uncommon", "rare": "Rare", "epic": "Epic", "legendary": "Legendary", "mythical": "Mythical", "unreal": "Unreal"}
# distinct colors for ultra rarities
RARITY_COLORS  = {"trash": 0x5d6d7e, "common": 0x95A5A6, "uncommon": 0x2ECC71, "rare": 0x3498DB, "epic": 0xF1C40F, "legendary": 0xD4AF37, "mythical": 0x8E44AD, "unreal": 0x00FFFF}

# ===== Cấu hình thời tiết =====
# Mỗi thời tiết có: tên, thời lượng (giây), tỉ lệ xuất hiện, buff, cá đặc biệt (nếu có)
WEATHER_CONFIG = {
    "clear": {
        "name": "Trời quang", "duration": 60, "rate": 0.5, "buff": {}, "special_fish": []
    },
    "rain": {
        "name": "Mưa", "duration": 180, "rate": 0.25, "buff": {"weight_mult": 1.10},
        "special_fish": [
            {"name": "Cá mưa", "emoji": "🌧️🐟", "rarity": "rare", "chance": 0.15, "base_weight": 8.0, "price_per_kg": 180}
        ]
    },
    "storm": {
        "name": "Bão", "duration": 180, "rate": 0.1, "buff": {"weight_mult": 1.25, "luck": 0.5},
        "special_fish": [
            {"name": "Cá sét", "emoji": "⚡🐟", "rarity": "epic", "chance": 0.08, "base_weight": 25.0, "price_per_kg": 950}
        ]
    },
    "fog": {
        "name": "Sương mù", "duration": 240, "rate": 0.15, "buff": {"luck": 0.2, "weight_mult": 1.05},
        "special_fish": [
            {"name": "Cá ma", "emoji": "👻🐟", "rarity": "epic", "chance": 0.12, "base_weight": 6.66, "price_per_kg": 777}
        ]
    },
    "meteor": {
        "name": "Mưa sao băng", "duration": 120, "rate": 0.01, "buff": {"shiny_mult": 3, "luck": 1.5, "weight_mult": 1.5}, "special_fish": []
    },
    "aurora": {
        "name": "Cực Quang", "duration": 120, "rate": 0.02, "buff": {"gem_mult": 2, "luck": 1.0, "weight_mult": 1.20},
        "special_fish": [
            {"name": "Cá Ánh Sáng", "emoji": "✨🐟", "rarity": "epic", "chance": 0.3, "base_weight": 3.5, "price_per_kg": 1500}
        ]
    }
}

# Weight class probabilities (tiny, normal, huge, gigantic)
WEIGHT_CLASS_PROBS = {"tiny": 0.15, "normal": 0.60, "huge": 0.23, "gigantic": 0.02}

# ===== Gem settings (mới) =====
GEM_SETTINGS = {
    # gem per caught fish by rarity
    "gem_per_rarity": {"epic": 5, "legendary": 10, "mythical": 15, "unreal": 50},
    # aurora weather multiplies gems
    "aurora_multiplier": 1,
    # daily gem range
    "daily_min": 40,
    "daily_max": 50,
    # default gem value if selling an item with no explicit gem price
    "sell_item_gems_default": 1,
}
# game_config.py
ROD_TIERS = {
    # 'luck' is added: rods now increase player's luck rather than fish count.
    1: {"name": "Cần Tre",        "cost": 0,     "luck": 0.0, "len_add": 0, "timeout_sub": 0.0},
    2: {"name": "Cần Gỗ",         "cost": 1000,  "luck": 3.5, "len_add": 4, "timeout_sub": 0.5},
    3: {"name": "Cần Sắt",        "cost": 10000, "luck": 8.0, "len_add": 6, "timeout_sub": 1.0},
    4: {"name": "Cần Carbon",     "cost": 50000, "luck": 13.0, "len_add": 9, "timeout_sub": 2.0},
    5: {"name": "Cần Huyền Thoại","cost": 200000, "luck": 20, "len_add": 15, "timeout_sub": 5.0, "gem_cost": 100},
    6: {"name": "Cần Thần Thoại", "cost": 1000000, "luck": 35.0, "len_add": 19, "timeout_sub": 9.0, "gem_cost": 300},
    7: {"name": "Cần Vô Cực",    "cost": 5000000, "luck": 50.0, "len_add": 21, "timeout_sub": 10.0, "gem_cost": 1000},
} 
MAX_ROD_LEVEL = max(ROD_TIERS)
XP_PER_CATCH = 10
BASE_XP_PER_LEVEL = 100

BASE_LUCK = 1

# Default price-per-kg by rarity (used if a fish entry doesn't override)
PRICE_PER_KG_BY_RARITY = {
    "trash": 5,
    "common": 10,
    "uncommon": 30,
    "rare": 120,
    "epic": 500,
    "legendary": 2000,
    "mythical": 10000,
    "unreal": 100000,
}
# Default weight ranges (kg) by rarity used to derive a base weight if fish doesn't provide one
WEIGHT_BY_RARITY = {
    "trash": (0.1, 1.0),
    "common": (0.2, 1.5),
    "uncommon": (0.5, 3.0),
    "rare": (1.0, 6.0),
    "epic": (2.0, 10.0),
    "legendary": (5.0, 40.0),
    "mythical": (10.0, 100.0),
    "unreal": (50.0, 500.0),
}

WEIGHT_CLASS_BOUNDS = {
    "tiny": 0.7,
    "normal": 1.1,
    "huge": 2.5,
    "gigantic": 7.0,
}

# Weight class boundaries and names (4 classes: tiny, normal, huge, gigantic)
WEIGHT_CLASS_NAMES = ["tiny", "normal", "huge", "gigantic"]
# Weight class percent ranges (applied to per-fish 'base_weight')
# Each fish may define an integer 'base_weight' (kg). The actual weight is base_weight * random_pct_in_range.
WEIGHT_CLASS_PCT_RANGES = {
    "tiny": (0.50, 0.70),
    "normal": (0.90, 1.10),
    "huge": (1.50, 2.50),
    "gigantic": (5.00, 7.00),
}

# Độ khó thử thách cơ bản (trước khi cộng/trừ theo rod)
BASE_CHALLENGE = {
    "len_min": 4,   # độ dài chuỗi emoji tối thiểu
    "len_max": 5,   # độ dài chuỗi emoji tối đa
    "timeout": 10,  # thời gian trả lời (giây)
}