# game_pets.py
# Định nghĩa pet trong game. Mỗi pet có:
# - id
# - name
# - emoji
# - desc
# - buffs: similar to items: fish_flat, timeout_add, len_sub, xp_flat, extra_slot

# Giới hạn số trứng có thể ấp cùng lúc
EGG_LIMIT = 3 


PETS = {
    "c1": {
        "name": "Chim Tép",
        "emoji": "🐤",
        "desc": "Tăng +1 luck.",
        "buffs": {"luck": 1},
        "rarity": "common",
    },
    "c2": {
        "name": "Rùa Con",
        "emoji": "<:Rua:1467796148155846656> ",
        "desc": "Tăng +1s thời gian.",
        "buffs": {"timeout_add": 1.0},
        "rarity": "common",
    },
    "c3": {
        "name": "Mèo",
        "emoji": "<:Kitty:1467947775198105754>",
        "desc": "Tăng +0.5s thời gian và +5 XP",
        "buffs": {"timeout_add": 0.5, "xp_flat": 5},
        "rarity": "common",
    },
    "u1": {
        "name": "Cá Vàng",
        "emoji": "🐠",
        "desc": "Tăng +10 XP mỗi lần.",
        "buffs": {"xp_flat": 10},
        "rarity": "uncommon",
    },
    "u2": {
        "name": "Bọ Cạp",
        "emoji": "🦂",
        "desc": "Tăng +2 luck.",
        "buffs": {"luck": 2},
        "rarity": "uncommon",
    },
    "r1": {
        "name": "Sếu Trắng",
        "emoji": "🕊️",
        "desc": "Giảm -2 ký tự thử thách.",
        "buffs": {"len_sub": 2},
        "rarity": "rare",
    },
    "r2": {
        "name": "Cá Mập",
        "emoji": "🦈",
        "desc": "Tăng +2s thời gian và +2.5 luck.",
        "buffs": {"timeout_add": 2.0, "luck": 2.5},
        "rarity": "rare",
    },
    "e1": {
        "name": "Rồng Nước",
        "emoji": "🐉",
        "desc": "Tăng +15 XP, +4 luck và x1.1 cân nặng.",
        "buffs": {"xp_flat": 15, "luck": 4, "weight_mult": 1.1},
        "rarity": "epic",
    },
    "e2": {
        "name": "Phượng Hoàng",
        "emoji": "🦚",
        "desc": "Tăng +2s thời gian và giảm -5 ký tự thử thách.",
        "buffs": {"timeout_add": 2.0, "len_sub": 5},
        "rarity": "epic",
    },
    "l1": {
        "name": "Cá Thần",
        "emoji": "🐬",
        "desc": "cho bạn +1 ô trang bị, tăng +2s thời gian và x1.3 cân nặng.",
        "buffs": {"extra_slot": 1, "timeout_add": 2.0, "weight_mult": 1.3},
        "rarity": "legendary",
    },
    "l2": {
        "name": "Kỳ Lân",
        "emoji": "🦄",
        "desc": "Tăng +40 XP và +2.5 luck.",
        "buffs": {"xp_flat": 40, "luck": 6},
        "rarity": "legendary",
    },
    "m1": {
        "name": "Phượng Hoàng Lửa",
        "emoji": "<:Phoenix:1467948781919273030>",
        "desc": "Tăng +5s thời gian, -5 ký tự, +6.0 luck và x1.5 cân nặng.",
        "buffs": {"timeout_add": 5.0, "len_sub": 5, "luck": 6.0, "weight_mult": 1.5},
        "rarity": "mythical",
    },
}

# Tiers: each tier maps to 3 pet ids (options when hatching)
EGG_TIERS = {
    1: ["c1", "c2", "c3", "u1"],
    2: ["c1", "c2","u2", "r1", "r2"],
    3: ["u2", "r1","r2", "e1", "e2", "l1"],
    4: ["e1", "e2", "l2", "l1", "m1"],  # tier 4 uses high tier pets as well
}

# Rarity weights when selecting from a tier (higher rarer less likely). This is a fallback; tiers may provide specific weighting.
RARITY_WEIGHTS = {
    "common": 70,
    "uncommon": 20,
    "rare": 9,
    "epic": 1,
    "legendary": 0.5,
    "mythical": 0.1,
}

# Display mapping for rarity: show single-letter representation when displaying pets
RARITY_LETTER = {
    "common": "C",
    "uncommon": "U",
    "rare": "R",
    "epic": "E",
    "legendary": "L",
    "mythical": "M",
}

# Order of rarities from low -> high (used for explicit sorting if needed)
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary", "mythical"]

# Egg shop: price and incubation time (seconds)
EGG_SHOP = {
    1: {"price": 200, "time": 60},       # 1 minute
    2: {"price": 1000, "time": 60 * 5},   # 5 minutes
    3: {"price": 4000, "time": 60 * 15}, # 15 minutes
    4: {"price": 50000, "time": 60 * 60 *2}, # 2 hour
}
