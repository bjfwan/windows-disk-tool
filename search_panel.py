"""
文件搜索面板组件
支持模糊搜索、路径搜索、大小过滤
"""
import customtkinter as ctk
from typing import Callable, List, Dict, Optional
from theme_colors import DARK_THEME, LIGHT_THEME


class SearchPanel(ctk.CTkFrame):
    """搜索面板组件"""
    
    def __init__(self, master, on_search: Optional[Callable] = None, **kwargs):
        """
        初始化搜索面板
        
        Args:
            master: 父组件
            on_search: 搜索回调函数 (search_query: str) -> None
        """
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.on_search = on_search
        self._create_ui()
    
    def _create_ui(self):
        """创建UI组件"""
        # 搜索框容器
        search_container = ctk.CTkFrame(
            self,
            fg_color=(LIGHT_THEME['bg_card'], DARK_THEME['bg_card']),
            corner_radius=12,
            border_width=1,
            border_color=(LIGHT_THEME['border_primary'], DARK_THEME['border_primary'])
        )
        search_container.pack(fill="x", padx=5, pady=5)
        
        # 搜索图标标签
        search_icon = ctk.CTkLabel(
            search_container,
            text="🔍",
            font=ctk.CTkFont(size=16),
            width=30
        )
        search_icon.pack(side="left", padx=(10, 0))
        
        # 搜索输入框
        self.search_entry = ctk.CTkEntry(
            search_container,
            placeholder_text="搜索文件夹名称或路径...",
            font=ctk.CTkFont(size=13),
            border_width=0,
            fg_color="transparent",
            height=40
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # 实时搜索 - 绑定按键事件
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)
        
        # 清除按钮
        self.clear_btn = ctk.CTkButton(
            search_container,
            text="✕",
            width=40,
            height=40,
            corner_radius=8,
            fg_color="transparent",
            hover_color=(LIGHT_THEME['bg_hover'], DARK_THEME['bg_hover']),
            text_color="gray",
            command=self.clear_search
        )
        self.clear_btn.pack(side="right", padx=5)
        self.clear_btn.pack_forget()  # 初始隐藏
        
        # 搜索选项区域（可展开）
        self.options_frame = ctk.CTkFrame(self, fg_color="transparent")
        # 初始不显示选项
        
    def _on_search_changed(self, event=None):
        """搜索框内容变化时触发"""
        query = self.search_entry.get().strip()
        
        # 显示/隐藏清除按钮
        if query:
            self.clear_btn.pack(side="right", padx=5)
        else:
            self.clear_btn.pack_forget()
        
        # 触发搜索回调
        if self.on_search:
            self.on_search(query)
    
    def clear_search(self):
        """清除搜索"""
        self.search_entry.delete(0, "end")
        self.clear_btn.pack_forget()
        if self.on_search:
            self.on_search("")
    
    def get_search_query(self) -> str:
        """获取当前搜索查询"""
        return self.search_entry.get().strip()


def fuzzy_match(text: str, query: str) -> bool:
    """
    模糊匹配算法
    
    Args:
        text: 要匹配的文本
        query: 搜索查询
    
    Returns:
        是否匹配
    
    Examples:
        fuzzy_match("System32", "sys") -> True
        fuzzy_match("Program Files", "prog") -> True
        fuzzy_match("Windows", "win") -> True
    """
    if not query:
        return True
    
    text_lower = text.lower()
    query_lower = query.lower()
    
    # 1. 直接包含匹配
    if query_lower in text_lower:
        return True
    
    # 2. 首字母缩写匹配（例如：pf 匹配 Program Files）
    words = text_lower.split()
    if len(words) > 1:
        initials = ''.join([w[0] for w in words if w])
        if query_lower in initials:
            return True
    
    # 3. 连续字符匹配（允许跳过字符）
    # 例如：prgm 可以匹配 Program
    query_idx = 0
    for char in text_lower:
        if query_idx < len(query_lower) and char == query_lower[query_idx]:
            query_idx += 1
    
    return query_idx == len(query_lower)


def filter_folders(folders: List[Dict], query: str) -> List[Dict]:
    """
    根据搜索查询过滤文件夹列表
    
    Args:
        folders: 文件夹列表
        query: 搜索查询
    
    Returns:
        匹配的文件夹列表
    """
    if not query:
        return folders
    
    query_lower = query.lower()
    results = []
    
    for folder in folders:
        # 检查文件夹名称
        if fuzzy_match(folder.get('name', ''), query):
            results.append(folder)
            continue
        
        # 检查路径
        if fuzzy_match(folder.get('path', ''), query):
            results.append(folder)
            continue
        
        # 检查父路径（用于显示在哪个父文件夹下）
        if fuzzy_match(folder.get('parent', ''), query):
            results.append(folder)
            continue
    
    return results


if __name__ == "__main__":
    # 测试模糊匹配
    test_cases = [
        ("System32", "sys", True),
        ("Program Files", "prog", True),
        ("Windows", "win", True),
        ("Documents and Settings", "docs", True),
        ("ProgramData", "pd", True),
        ("Recovery", "rec", True),
        ("Users", "u", True),
        ("Temp", "t", True),
    ]
    
    print("模糊匹配测试：")
    for text, query, expected in test_cases:
        result = fuzzy_match(text, query)
        status = "✓" if result == expected else "✗"
        print(f"{status} {text} ~ {query} -> {result}")
