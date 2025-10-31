import customtkinter as ctk
from typing import Callable, Optional
from theme_colors import DARK_THEME, LIGHT_THEME, get_usage_color
from animations import AnimationHelper, AnimatedProgressBar

class GlassFrame(ctk.CTkFrame):
    """毛玻璃效果框架 - 2.0增强版"""
    def __init__(self, master, **kwargs):
        # 使用新的配色系统
        fg_color = kwargs.pop('fg_color', (LIGHT_THEME['bg_card'], DARK_THEME['bg_card']))
        corner_radius = kwargs.pop('corner_radius', 16)
        border_width = kwargs.pop('border_width', 1)
        border_color = kwargs.pop('border_color', (LIGHT_THEME['border_primary'], DARK_THEME['border_primary']))
        
        super().__init__(
            master,
            fg_color=fg_color,
            corner_radius=corner_radius,
            border_width=border_width,
            border_color=border_color,
            **kwargs
        )

class DriveCard(GlassFrame):
    """磁盘卡片组件"""
    def __init__(self, master, drive_data: dict, on_analyze: Optional[Callable] = None):
        super().__init__(master, corner_radius=12)
        
        self.drive_data = drive_data
        self.on_analyze = on_analyze
        
        # 驱动器标签
        drive_letter = drive_data['letter']
        percent = drive_data['percent']
        
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 5))
        
        # 驱动器图标和名称
        title = ctk.CTkLabel(
            header,
            text=f"💾 {drive_letter}",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.pack(side="left")
        
        # 使用率标签 - 使用新配色
        usage_colors = get_usage_color(percent)
        usage_label = ctk.CTkLabel(
            header,
            text=f"{percent:.1f}%",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=usage_colors
        )
        usage_label.pack(side="right")
        
        # 进度条 - 使用渐变色效果和动画（C3增强）
        if percent > 90:
            progress_color = (LIGHT_THEME['accent_red'], DARK_THEME['accent_red'])
        elif percent > 70:
            progress_color = (LIGHT_THEME['accent_orange'], DARK_THEME['accent_orange'])
        else:
            progress_color = (LIGHT_THEME['accent_green'], DARK_THEME['accent_green'])
        
        progress = AnimatedProgressBar(
            self, 
            height=14, 
            corner_radius=7,
            progress_color=progress_color
        )
        progress.pack(fill="x", padx=15, pady=5)
        # 使用动画效果设置进度（缩短动画时间以减少卡顿）
        progress.set_animated(percent / 100, duration_ms=300)
        
        # 空间信息
        used_gb = drive_data['used'] / (1024**3)
        free_gb = drive_data['free'] / (1024**3)
        total_gb = drive_data['total'] / (1024**3)
        
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=15, pady=(5, 10))
        
        info_text = f"可用: {free_gb:.1f}GB  |  总计: {total_gb:.1f}GB"
        info_label = ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        info_label.pack(side="left")
        
        # 分析按钮（所有磁盘都可分析）- 使用新配色
        if on_analyze:
            analyze_btn = ctk.CTkButton(
                info_frame,
                text="📊 分析",
                width=80,
                height=32,
                command=lambda: on_analyze(drive_letter),
                font=ctk.CTkFont(size=12, weight="bold"),
                corner_radius=8,
                fg_color=(LIGHT_THEME['accent_blue'], DARK_THEME['accent_blue']),
                hover_color=("#3d85e6", "#3d85e6")
            )
            analyze_btn.pack(side="right", padx=5)

class FolderItem(ctk.CTkFrame):
    """文件夹项组件（带复选框和展开）- 2.0增强版"""
    def __init__(self, master, folder_data: dict, on_toggle: Optional[Callable] = None, 
                 format_size_func: Optional[Callable] = None, on_expand: Optional[Callable] = None,
                 level: int = 0):
        # 使用新配色系统
        super().__init__(
            master, 
            fg_color=(LIGHT_THEME['bg_secondary'], DARK_THEME['bg_secondary']), 
            corner_radius=10
        )
        
        self.folder_data = folder_data
        self.selected = ctk.BooleanVar(value=False)
        self.on_expand = on_expand
        self.level = level
        self.expanded = False
        self.sub_items_frame = None
        
        # 左侧容器：缩进+展开按钮+复选框
        left_container = ctk.CTkFrame(self, fg_color="transparent")
        left_container.pack(side="left", padx=(10 + level * 20, 0), pady=10)
        
        # 展开按钮（如果有子项）- 使用新配色
        if folder_data.get('has_children', True):
            self.expand_btn = ctk.CTkButton(
                left_container,
                text="▶",
                width=28,
                height=28,
                command=self.toggle_expand,
                font=ctk.CTkFont(size=12),
                fg_color="transparent",
                hover_color=(LIGHT_THEME['bg_hover'], DARK_THEME['bg_hover']),
                text_color=(LIGHT_THEME['text_secondary'], DARK_THEME['text_secondary'])
            )
            self.expand_btn.pack(side="left", padx=(0, 5))
        
        # 复选框
        self.checkbox = ctk.CTkCheckBox(
            left_container,
            text="",
            variable=self.selected,
            command=lambda: on_toggle(folder_data, self.selected.get()) if on_toggle else None,
            width=30
        )
        self.checkbox.pack(side="left")
        
        # 信息区域
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        # 文件夹名称
        name_label = ctk.CTkLabel(
            info_frame,
            text=f"📁 {folder_data['name']}",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        name_label.pack(anchor="w")
        
        # 大小和路径
        if format_size_func:
            size_str = format_size_func(folder_data['size'])
        else:
            size_str = f"{folder_data['size'] / (1024**3):.2f} GB"
        
        path_label = ctk.CTkLabel(
            info_frame,
            text=f"大小: {size_str} | 路径: {folder_data['path']}",
            font=ctk.CTkFont(size=10),
            text_color="gray",
            anchor="w"
        )
        path_label.pack(anchor="w")
    
    def set_selected(self, value: bool):
        """设置选中状态"""
        self.selected.set(value)
    
    def toggle_expand(self):
        """切换展开/收起"""
        if self.expanded:
            # 收起 - 删除所有子项
            self.collapse()
        else:
            # 展开
            if self.on_expand:
                if hasattr(self, 'expand_btn'):
                    self.expand_btn.configure(text="▼")
                self.expanded = True
                # 调用展开回调
                self.on_expand(self.folder_data, self)
    
    def collapse(self):
        """收起子项"""
        # 删除所有子项widgets
        if hasattr(self, 'sub_items'):
            for item in self.sub_items:
                item.destroy()
            self.sub_items = []
        
        if hasattr(self, 'expand_btn'):
            self.expand_btn.configure(text="▶")
        self.expanded = False

class ProgressPanel(GlassFrame):
    """进度面板组件 - 2.0增强版"""
    def __init__(self, master):
        super().__init__(master, corner_radius=16)
        
        title = ctk.CTkLabel(
            self,
            text="📝 操作日志",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=(LIGHT_THEME['text_primary'], DARK_THEME['text_primary'])
        )
        title.pack(pady=(12, 8))
        
        # 使用新配色的文本框
        self.log_text = ctk.CTkTextbox(
            self, 
            height=250, 
            font=ctk.CTkFont(size=13),
            corner_radius=10,
            border_width=1,
            border_color=(LIGHT_THEME['border_primary'], DARK_THEME['border_primary'])
        )
        self.log_text.pack(padx=12, pady=(0, 12), fill="both", expand=True)
        self.log_text.insert("1.0", "✨ 等待操作...\n")
        self.log_text.configure(state="disabled")
    
    def log(self, message: str):
        """添加日志（极致性能版 - 最小化UI操作）"""
        # 此方法现在由main.py的异步日志处理器直接调用
        # 保留兼容性
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"{message}\n")
            lines = int(self.log_text.index('end-1c').split('.')[0])
            if lines > 200:
                self.log_text.delete('1.0', f'{lines-200}.0')
            if lines % 20 == 0:
                self.log_text.see("end")
            self.log_text.configure(state="disabled")
        except:
            pass
    
    def clear(self):
        """清空日志"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

class DriveAnalysisPanel(GlassFrame):
    """磁盘分析面板 - 2.0增强版"""
    def __init__(self, master, format_size_func: Callable):
        super().__init__(master, corner_radius=16)
        self.format_size = format_size_func
        
        # 标题
        self.title_label = ctk.CTkLabel(
            self,
            text="📊 磁盘分析",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=(LIGHT_THEME['text_primary'], DARK_THEME['text_primary'])
        )
        self.title_label.pack(pady=(12, 8))
        
        # 统计信息 - 使用新配色
        self.stats_frame = ctk.CTkFrame(
            self, 
            fg_color=(LIGHT_THEME['bg_secondary'], DARK_THEME['bg_secondary']), 
            corner_radius=12,
            border_width=1,
            border_color=(LIGHT_THEME['border_primary'], DARK_THEME['border_primary'])
        )
        self.stats_frame.pack(fill="x", padx=12, pady=8)
        
        self.stats_label = ctk.CTkLabel(
            self.stats_frame,
            text="⏳ 正在扫描...",
            font=ctk.CTkFont(size=12),
            justify="left",
            text_color=(LIGHT_THEME['text_secondary'], DARK_THEME['text_secondary'])
        )
        self.stats_label.pack(pady=12, padx=12)
        
        # Top文件夹标题
        top_title = ctk.CTkLabel(
            self,
            text="🗂️ 占用空间最多的文件夹",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        top_title.pack(pady=(10, 5))
        
        # 滚动列表
        self.scroll_frame = ctk.CTkScrollableFrame(self, height=200)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def update_analysis(self, analysis: dict):
        """更新分析显示"""
        # 更新统计
        total_gb = analysis['total_size'] / (1024**3)
        used_gb = analysis['used_size'] / (1024**3)
        free_gb = analysis['free_size'] / (1024**3)
        percent = analysis['percent']
        scanned_gb = analysis.get('scanned_total', 0) / (1024**3)
        
        stats_text = f"总容量: {total_gb:.1f} GB\n"
        stats_text += f"已使用: {used_gb:.1f} GB ({percent:.1f}%)\n"
        stats_text += f"可用: {free_gb:.1f} GB\n"
        stats_text += f"已扫描: {scanned_gb:.1f} GB"
        
        self.stats_label.configure(text=stats_text)
        
        # 清空并更新Top文件夹
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        for idx, folder in enumerate(analysis.get('top_folders', [])[:15], 1):
            # 使用新配色
            folder_frame = ctk.CTkFrame(
                self.scroll_frame, 
                fg_color=(LIGHT_THEME['bg_secondary'], DARK_THEME['bg_secondary']), 
                corner_radius=8,
                border_width=1,
                border_color=(LIGHT_THEME['border_secondary'], DARK_THEME['border_secondary'])
            )
            folder_frame.pack(fill="x", padx=5, pady=3)
            
            size_str = self.format_size(folder['size'])
            percent_str = f"{folder.get('percent_of_disk', 0):.1f}%"
            
            name_label = ctk.CTkLabel(
                folder_frame,
                text=f"{idx}. {folder['name']}",
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w",
                text_color=(LIGHT_THEME['text_primary'], DARK_THEME['text_primary'])
            )
            name_label.pack(side="left", padx=12, pady=8)
            
            # 根据是否为系统文件夹选择颜色
            if folder.get('is_system'):
                size_color = (LIGHT_THEME['accent_red'], DARK_THEME['accent_red'])
            else:
                size_color = (LIGHT_THEME['accent_blue'], DARK_THEME['accent_blue'])
            
            size_label = ctk.CTkLabel(
                folder_frame,
                text=f"{size_str} ({percent_str})",
                font=ctk.CTkFont(size=10),
                text_color=size_color
            )
            size_label.pack(side="right", padx=12, pady=8)
