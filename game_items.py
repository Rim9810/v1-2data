# game_items.py
# Định nghĩa các vật phẩm (cổ vật) trong game.
# Mỗi item có:
# - id: khóa duy nhất (dùng để trang bị nhanh)
# - name: tên hiển thị
# - emoji: hiển thị
# - desc: mô tả
# - buffs: dictionary, các hiệu ứng đơn giản (ví dụ: xp_flat tăng XP, money_pct tăng tiền khi bán)
# - sellable: bool (các cổ vật thường không bán được)

ITEMS = {
    "01": {
        "name": "Tượng Cổ",
        "emoji": "🗿",
        "desc": "Tượng cổ từ nền văn minh xa xưa. Tăng +30 XP, +1.0 luck và x1.1 cân nặng.",
        "buffs": {"xp_flat": 30, "luck": 1.0, "weight_mult": 1.1},
        "sellable": True,
        "sell_gems": 500,
        "buy_gems": 2000,
    },
    "02": {
        "name": "Tất của Nhy",
        "emoji": "🧦",
        "desc": "Tất đặc biệt của Nhy. Tăng +20 XP, +0.5 luck và giảm thời gian chờ giữa các lần câu cá.",
        "buffs": {"xp_flat": 20, "luck": 0.5, "timeout_add": 2.0},
        "sellable": True,
        "sell_gems": 500,
        "buy_gems": 2000,
    },
    "03": {
        "name": "Bình Cổ",
        "emoji": "🧿",
        "desc": "Bình cổ từ nền văn minh xa xưa. Tăng tỷ lệ cá hiếm và giảm độ dài thử thách.",
        "buffs": {"luck": 0.8, "timeout_add": 1.5, "len_sub": 2},
        "sellable": True,
        "sell_gems": 500,
        "buy_gems": 2000,
    },
    "04": {
        "name": "San Hô Huyền Bí",
        "emoji": "🪸",
        "desc": "San hô từ thời cổ đại. Tăng mạnh thời gian nhập chuỗi mỗi lần câu cá.",
        "buffs": {"timeout_add": 5.0, "len_sub": 1},
        "sellable": True,
        "sell_gems": 500,
        "buy_gems": 2000,
    },
    "05": {
        "name": "Ngọc Thủy",
        "emoji": "💠",
        "desc": "Viên ngọc từ đáy đại dương. Tăng +1.5 luck và giảm 5 ký tự thử thách.",
        "buffs": {"luck": 1.5, "len_sub": 3},
        "sellable": True,
        "sell_gems": 500,
        "buy_gems": 2000,
    },
} 
