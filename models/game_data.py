"""游戏数据 - 作物信息、等级经验等静态数据"""

# 作物数据表：(名称, 种子ID, 解锁等级, 总生长时间秒, 经验, 果实数量)
# 按解锁等级排序，从 Plant.json 提取
CROPS = [
    ("白萝卜", 20002, 1, 60, 1, 5),
    ("胡萝卜", 20003, 2, 120, 2, 10),
    ("大白菜", 20059, 3, 300, 5, 20),
    ("大蒜", 20065, 4, 600, 10, 20),
    ("大葱", 20064, 5, 1200, 20, 30),
    ("水稻", 20060, 6, 2400, 41, 30),
    ("小麦", 20061, 7, 3600, 62, 40),
    ("玉米", 20004, 8, 4800, 82, 40),
    ("鲜姜", 20066, 9, 6000, 106, 60),
    ("土豆", 20005, 10, 7200, 128, 60),
    ("小白菜", 20071, 11, 9000, 160, 80),
    ("生菜", 20096, 12, 10800, 192, 80),
    ("油菜", 20099, 13, 14400, 272, 200),
    ("茄子", 20006, 14, 28800, 544, 200),
    ("红枣", 20051, 15, 43200, 816, 200),
    ("蒲公英", 20120, 16, 86400, 1632, 200),
    ("银莲花", 20259, 17, 14400, 288, 200),
    ("番茄", 20007, 18, 28800, 576, 200),
    ("花菜", 20098, 19, 43200, 864, 200),
    ("韭菜", 20305, 20, 86400, 1728, 200),
    ("小雏菊", 20105, 21, 14400, 304, 200),
    ("豌豆", 20008, 22, 28800, 608, 200),
    ("莲藕", 20037, 23, 43200, 912, 200),
    ("红玫瑰", 20041, 24, 86400, 1824, 200),
    ("秋菊(黄)", 20161, 25, 14400, 324, 200),
    ("满天星", 20110, 26, 28800, 648, 200),
    ("含羞草", 20143, 27, 43200, 972, 200),
    ("牵牛花", 20147, 28, 86400, 1944, 200),
    ("秋菊(红)", 20162, 29, 14400, 344, 200),
    ("辣椒", 20009, 30, 28800, 688, 200),
    ("黄瓜", 20097, 31, 43200, 1032, 200),
    ("芹菜", 20306, 32, 86400, 2064, 200),
    ("天香百合", 20103, 33, 14400, 368, 200),
]


def get_crop_names() -> list[str]:
    """获取所有作物名称列表"""
    return [c[0] for c in CROPS]


def get_crops_for_level(level: int) -> list[tuple]:
    """获取指定等级可种植的作物"""
    return [c for c in CROPS if c[2] <= level]


def get_crop_by_name(name: str) -> tuple | None:
    """根据名称查找作物"""
    for c in CROPS:
        if c[0] == name:
            return c
    return None


def get_best_crop_for_level(level: int) -> tuple | None:
    """获取当前等级下单位时间经验最高的作物

    计算公式：经验 / 生长时间（秒），值越大效率越高。
    """
    available = get_crops_for_level(level)
    if not available:
        return None
    return max(available, key=lambda c: c[4] / c[3])



def get_crop_index_in_list(name: str, level: int) -> int:
    """获取指定作物在当前等级可种列表中的位置索引（从0开始）

    游戏中点击空地后弹出的种子列表是按解锁等级排序的。
    返回该作物在列表中的位置，用于相对位置点击。
    返回 -1 表示未找到。
    """
    available = get_crops_for_level(level)
    for i, c in enumerate(available):
        if c[0] == name:
            return i
    return -1


def format_grow_time(seconds: int) -> str:
    """格式化生长时间"""
    if seconds < 60:
        return f"{seconds}秒"
    if seconds < 3600:
        return f"{seconds // 60}分钟"
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    return f"{hours}小时{mins}分" if mins else f"{hours}小时"


def get_crop_display_info() -> list[str]:
    """获取作物显示信息列表，用于下拉框"""
    items = []
    for name, _, level, grow_time, exp, _ in CROPS:
        time_str = format_grow_time(grow_time)
        items.append(f"{name} (Lv{level}, {time_str}, {exp}经验)")
    return items
