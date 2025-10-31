"""
主题配色系统 2.0 - 现代化深色主题
"""

# 深色主题增强配色
DARK_THEME = {
    # 背景色
    'bg_primary': '#0a0e1a',      # 深蓝黑背景
    'bg_secondary': '#1a1f2e',    # 次要背景
    'bg_card': '#252d3f',         # 卡片背景
    'bg_hover': '#2a3448',        # 悬停背景
    
    # 强调色
    'accent_blue': '#4a9eff',     # 主蓝色
    'accent_green': '#00d9a3',    # 成功绿
    'accent_orange': '#ff9f43',   # 警告橙
    'accent_red': '#ee5a6f',      # 危险红
    'accent_purple': '#a855f7',   # 紫色
    
    # 文本色
    'text_primary': '#ffffff',    # 主文本
    'text_secondary': '#a0a8b8',  # 次要文本
    'text_muted': '#6c7585',      # 弱化文本
    'text_success': '#00d9a3',    # 成功文本
    'text_warning': '#ff9f43',    # 警告文本
    'text_error': '#ee5a6f',      # 错误文本
    
    # 边框色
    'border_primary': '#2a3449',  # 主边框
    'border_secondary': '#1f2433', # 次要边框
}

# 浅色主题配色（兼容）
LIGHT_THEME = {
    'bg_primary': '#f5f7fa',
    'bg_secondary': '#ffffff',
    'bg_card': '#ffffff',
    'bg_hover': '#e8ecf1',
    
    'accent_blue': '#2196f3',
    'accent_green': '#4caf50',
    'accent_orange': '#ff9800',
    'accent_red': '#f44336',
    'accent_purple': '#9c27b0',
    
    'text_primary': '#1a1f2e',
    'text_secondary': '#6c7585',
    'text_muted': '#a0a8b8',
    'text_success': '#4caf50',
    'text_warning': '#ff9800',
    'text_error': '#f44336',
    
    'border_primary': '#e0e5ea',
    'border_secondary': '#f0f2f5',
}

# 渐变方案
GRADIENTS = {
    'primary': ['#4a9eff', '#00d9a3'],        # 蓝到绿
    'success': ['#00d9a3', '#00b386'],        # 绿色渐变
    'warning': ['#ff9f43', '#ee5a6f'],        # 橙到红
    'disk_usage_low': ['#00d9a3', '#4a9eff'], # 低使用率（绿到蓝）
    'disk_usage_mid': ['#ffeb3b', '#ff9f43'], # 中使用率（黄到橙）
    'disk_usage_high': ['#ff9f43', '#ee5a6f'], # 高使用率（橙到红）
}

# 组件样式配置
BUTTON_STYLES = {
    'primary': {
        'fg_color': ('accent_blue', 'accent_blue'),
        'hover_color': ('#3d85e6', '#3d85e6'),
        'text_color': ('text_primary', 'text_primary'),
        'border_width': 0,
        'corner_radius': 12,
        'height': 36,
    },
    'secondary': {
        'fg_color': 'transparent',
        'border_color': ('accent_blue', 'accent_blue'),
        'border_width': 2,
        'hover_color': ('bg_hover', 'bg_hover'),
        'corner_radius': 12,
        'height': 36,
    },
    'success': {
        'fg_color': ('accent_green', 'accent_green'),
        'hover_color': ('#00c292', '#00c292'),
        'text_color': ('text_primary', 'text_primary'),
        'border_width': 0,
        'corner_radius': 12,
        'height': 36,
    },
    'warning': {
        'fg_color': ('accent_orange', 'accent_orange'),
        'hover_color': ('#e68a3c', '#e68a3c'),
        'text_color': ('text_primary', 'text_primary'),
        'border_width': 0,
        'corner_radius': 12,
        'height': 36,
    },
}

CARD_STYLES = {
    'default': {
        'fg_color': ('bg_card', 'bg_card'),
        'corner_radius': 16,
        'border_width': 1,
        'border_color': ('border_primary', 'border_primary'),
    },
    'elevated': {
        'fg_color': ('bg_card', 'bg_card'),
        'corner_radius': 16,
        'border_width': 2,
        'border_color': ('accent_blue', 'accent_blue'),
    },
}

def get_color(theme: dict, key: str, mode: str = 'dark') -> str:
    """获取主题颜色
    
    Args:
        theme: 主题字典（DARK_THEME 或 LIGHT_THEME）
        key: 颜色键
        mode: 'dark' 或 'light'
    
    Returns:
        颜色值
    """
    if mode == 'dark':
        return DARK_THEME.get(key, '#ffffff')
    else:
        return LIGHT_THEME.get(key, '#000000')

def get_usage_color(percent: float) -> tuple:
    """根据使用率获取颜色（返回文本颜色元组）
    
    Args:
        percent: 使用率百分比
    
    Returns:
        (light_mode_color, dark_mode_color)
    """
    if percent > 90:
        return (LIGHT_THEME['text_error'], DARK_THEME['accent_red'])
    elif percent > 70:
        return (LIGHT_THEME['text_warning'], DARK_THEME['accent_orange'])
    else:
        return (LIGHT_THEME['text_success'], DARK_THEME['accent_green'])

def get_gradient_colors(gradient_name: str) -> list:
    """获取渐变颜色列表
    
    Args:
        gradient_name: 渐变名称
    
    Returns:
        颜色列表 [start_color, end_color]
    """
    return GRADIENTS.get(gradient_name, GRADIENTS['primary'])
