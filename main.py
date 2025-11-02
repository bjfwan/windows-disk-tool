import customtkinter as ctk
from tkinter import messagebox
import threading
import os
import time
import tkinter as tk
import subprocess
import webbrowser
from queue import Queue
from disk_scanner import DiskScanner
from file_mover import FileMover
from scanner_engine import ScannerEngine
from ui_components import GlassFrame, DriveCard, FolderItem, ProgressPanel, DriveAnalysisPanel
from search_panel import SearchPanel, filter_folders
from scan_cache import ScanCache
import dialogs

# 常量定义
MIN_MOVABLE_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BUFFER_SIZE = 50
FOLDER_DISPLAY_LIMIT = 200
SELECT_ALL_LIMIT = 100

# 设置外观
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class DiskMigrationApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 窗口基本设置
        self.title("磁盘迁移工具 Pro v2.0")
        self.geometry("1600x900")
        
        # 窗口居中
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (1600 // 2)
        y = (self.winfo_screenheight() // 2) - (900 // 2)
        self.geometry(f"1600x900+{x}+{y}")
        
        # 初始化缓存系统
        self.cache = ScanCache(expire_hours=24)
        
        # 启用Windows备份权限（允许读取所有文件）
        try:
            from privilege_manager import enable_all_privileges
            if enable_all_privileges():
                print("✅ 已启用Windows备份权限，可读取所有文件")
            else:
                print("⚠️ 未能启用备份权限，某些系统文件可能无法访问")
        except Exception as e:
            print(f"⚠️ 权限管理器初始化失败: {e}")
        
        # 初始化扫描器
        self.scanner = DiskScanner()
        self.mover = FileMover()
        
        # 根据CPU核心数动态设置线程数（智能自适应）
        cpu_count = os.cpu_count() or 4
        # 智能线程数：核心数 × 2，最少8个，最多32个
        optimal_workers = min(max(cpu_count * 2, 8), 32)
        self.engine = ScannerEngine(max_workers=optimal_workers, cache=self.cache)
        
        # 先不记录日志，等UI创建后再记录
        self.startup_workers = optimal_workers
        
        # 窗口配置
        self.title("💾 磁盘迁移工具 Pro")
        self.geometry("1500x850")
        self.configure(fg_color=("gray95", "gray10"))
        
        # 检查管理员权限
        if not self.scanner.is_admin():
            messagebox.showwarning("权限提示", "建议以管理员身份运行！\n某些功能可能受限。")
        
        # 数据存储
        self.drives_data = []
        self.folders_data = []
        self.selected_folders = []
        self.selected_target_drive = None
        self.drive_analyses = {}  # 存储各磁盘的分析结果
        
        # UI组件引用
        self.folder_items = []
        self.progress_panel = None
        
        # 异步日志队列（彻底消除UI卡顿）
        self.log_queue = Queue()
        self.log_running = True
        self._start_log_processor()
        
        # 创建UI
        self.create_ui()
        
        # 绑定快捷键（C2增强）
        self.bind_shortcuts()
        
        # 绑定窗口大小变化事件（C4增强）
        self.bind("<Configure>", self.on_window_resize)
        self.current_layout_mode = "three-column"  # 当前布局模式
        
        # 绑定窗口关闭事件，优化关闭响应速度
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 显示启动信息
        self.log(f"⚡ 已启用 {self.startup_workers} 线程并行扫描")
        self.log("💡 快捷键: Ctrl+A全选 | Ctrl+D取消 | F5刷新 | Ctrl+Z撤销")
        
        # 首次启动欢迎弹窗
        self.show_first_run_dialog()
        
        # 自动开始扫描
        self.after(100, self.quick_scan)
    
    def _update_movable_folders(self, analysis_data: dict, log_suffix: str = ""):
        """提取并更新可移动文件夹列表（抽取重复逻辑）"""
        all_folders = analysis_data.get('folders', [])
        # 确保有movable字段
        for folder in all_folders:
            if 'movable' not in folder:
                folder['movable'] = not folder.get('is_system', False) and folder.get('size', 0) > MIN_MOVABLE_SIZE
        
        self.folders_data = [f for f in all_folders if f.get('movable', False)]
        self.after(0, self.update_folder_display)
        
        suffix = f"（{log_suffix}）" if log_suffix else ""
        self.log(f"✓ 找到 {len(self.folders_data)} 个可移动文件夹{suffix}")
    
    def create_ui(self):
        """创建现代化UI"""
        
        # ========== 顶部标题栏 ==========
        header = GlassFrame(self, height=80, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)
        
        # 左侧标题
        title_container = ctk.CTkFrame(header, fg_color="transparent")
        title_container.pack(side="left", padx=25)
        
        title = ctk.CTkLabel(
            title_container,
            text="💾 磁盘迁移工具 Pro",
            font=ctk.CTkFont(size=26, weight="bold")
        )
        title.pack(anchor="w")
        
        subtitle = ctk.CTkLabel(
            title_container,
            text="多线程智能扫描 | 批量文件迁移 | 安全符号链接",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        subtitle.pack(anchor="w")
        
        # 右侧按钮组
        btn_container = ctk.CTkFrame(header, fg_color="transparent")
        btn_container.pack(side="right", padx=25)
        dev_btn = ctk.CTkButton(
            btn_container,
            text="👨‍💻 开发者",
            command=self.show_first_run_dialog_manual,
            width=100,
            height=38,
            fg_color=("purple", "darkviolet"),
            hover_color=("darkviolet", "purple"),
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=10
        )
        dev_btn.grid(row=0, column=0, padx=3)
        
        refresh_btn = ctk.CTkButton(
            btn_container,
            text="🔄 快速扫描",
            command=self.quick_scan,
            width=120,
            height=38,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=10
        )
        refresh_btn.grid(row=0, column=1, padx=3)
        
        deep_scan_btn = ctk.CTkButton(
            btn_container,
            text="🔬 深度扫描",
            command=self.deep_scan,
            width=120,
            height=38,
            fg_color=("blue", "darkblue"),
            hover_color=("darkblue", "blue"),
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=10
        )
        deep_scan_btn.grid(row=0, column=2, padx=3)
        
        restore_btn = ctk.CTkButton(
            btn_container,
            text="↶ 恢复",
            command=self.undo_move,
            width=100,
            height=38,
            fg_color="orange",
            hover_color="darkorange",
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=10
        )
        restore_btn.grid(row=0, column=3, padx=3)
        
        update_btn = ctk.CTkButton(
            btn_container,
            text="📝 更新记录",
            command=self.show_update_log,
            width=110,
            height=38,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=10
        )
        update_btn.grid(row=0, column=4, padx=3)
        
        # ========== 主内容区 ==========
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=15, pady=(15, 5))
        
        # 左栏：磁盘状态和分析
        left_column = ctk.CTkFrame(main_container, fg_color="transparent", width=400)
        left_column.pack(side="left", fill="both", padx=(0, 8))
        left_column.pack_propagate(False)
        
        # 磁盘卡片区域
        disk_title = ctk.CTkLabel(
            left_column,
            text="💿 所有磁盘",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        disk_title.pack(pady=(0, 10))
        
        self.disk_container = ctk.CTkScrollableFrame(left_column, fg_color="transparent", height=250)
        self.disk_container.pack(fill="x", pady=(0, 10))
        
        # 磁盘分析面板（放在磁盘卡片下方）
        self.analysis_panel = DriveAnalysisPanel(left_column, self.scanner.format_size)
        self.analysis_panel.pack(fill="both", expand=True)
        
        # 中部：文件夹列表（占据最大空间）
        center_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        center_frame.pack(side="left", fill="both", expand=True, padx=(8, 4))
        
        folder_panel = GlassFrame(center_frame, corner_radius=16)
        folder_panel.pack(side="left", fill="both", expand=True, padx=(8, 4))
        
        # 标题
        folder_title_frame = ctk.CTkFrame(folder_panel, fg_color="transparent")
        folder_title_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        folder_title = ctk.CTkLabel(
            folder_title_frame,
            text="📂 可移动文件夹",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        folder_title.pack(side="left")
        
        # 添加搜索面板和选择按钮
        control_row = ctk.CTkFrame(folder_panel, fg_color="transparent")
        control_row.pack(fill="x", padx=15, pady=(0, 10))
        
        # 左侧：搜索面板
        search_container = ctk.CTkFrame(control_row, fg_color="transparent")
        search_container.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_panel = SearchPanel(search_container, on_search=self._on_search)
        self.search_panel.pack(fill="x")
        
        # 右侧：选择按钮
        btn_frame = ctk.CTkFrame(control_row, fg_color="transparent")
        btn_frame.pack(side="right")
        
        select_all_btn = ctk.CTkButton(
            btn_frame,
            text="☑ 全选",
            command=lambda: [self.log("🔘 点击了全选按钮"), self.select_all()],
            width=75,
            height=40,
            corner_radius=8
        )
        select_all_btn.pack(side="left", padx=3)
        
        clear_btn = ctk.CTkButton(
            btn_frame,
            text="☐ 清空",
            command=lambda: [self.log("🔘 点击了清空按钮"), self.clear_selection()],
            width=75,
            height=40,
            corner_radius=8
        )
        clear_btn.pack(side="left", padx=3)
        
        # 文件夹列表
        self.folder_container = ctk.CTkScrollableFrame(folder_panel, fg_color="transparent")
        self.folder_container.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        
        # 选中统计
        self.selection_label = ctk.CTkLabel(
            folder_panel,
            text="已选择: 0 个 | 总大小: 0 GB",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.selection_label.pack(pady=(0, 10))
        
        # 右栏：操作面板
        right_column = ctk.CTkFrame(main_container, fg_color="transparent", width=400)
        right_column.pack(side="right", fill="both", padx=(8, 0))
        right_column.pack_propagate(False)
        
        # 操作控制面板
        control_panel = GlassFrame(right_column, corner_radius=12)
        control_panel.pack(fill="x", pady=(0, 10))
        
        control_title = ctk.CTkLabel(
            control_panel,
            text="⚙️ 移动控制",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        control_title.pack(pady=(15, 10))
        
        # 目标磁盘选择
        target_label = ctk.CTkLabel(
            control_panel,
            text="目标磁盘:",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        target_label.pack(pady=(5, 5))
        
        self.target_var = ctk.StringVar(value="请先扫描")
        self.target_menu = ctk.CTkOptionMenu(
            control_panel,
            variable=self.target_var,
            values=["请先扫描"],
            command=self.on_target_selected,
            font=ctk.CTkFont(size=12),
            width=300
        )
        self.target_menu.pack(padx=15, pady=5)
        
        # 符号链接选项
        self.link_var = ctk.BooleanVar(value=True)
        link_check = ctk.CTkCheckBox(
            control_panel,
            text="创建符号链接（保持兼容性）",
            variable=self.link_var,
            font=ctk.CTkFont(size=12)
        )
        link_check.pack(pady=10)
        
        # 移动按钮
        self.move_btn = ctk.CTkButton(
            control_panel,
            text="🚀 批量移动",
            command=self.start_batch_move,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=("green", "darkgreen"),
            hover_color=("darkgreen", "green"),
            corner_radius=10
        )
        self.move_btn.pack(padx=15, pady=(10, 20), fill="x")
        self.move_btn.configure(state="disabled")
        
        # 日志面板
        self.progress_panel = ProgressPanel(right_column)
        self.progress_panel.pack(fill="both", expand=True)
    
    def _start_log_processor(self):
        """启动异步日志处理器（后台线程 - 超级优化版）"""
        def process_logs():
            buffer = []
            last_update = time.time()
            
            while self.log_running:
                try:
                    # 非阻塞获取日志 - 降低批量大小到LOG_BUFFER_SIZE
                    while not self.log_queue.empty() and len(buffer) < LOG_BUFFER_SIZE:
                        msg = self.log_queue.get_nowait()
                        buffer.append(msg)
                    
                    # 每5秒或缓冲区满时更新UI（大幅降低更新频率）
                    current_time = time.time()
                    should_update = (
                        len(buffer) >= LOG_BUFFER_SIZE or
                        (buffer and current_time - last_update >= 5.0)  # 2秒→5秒
                    )
                    
                    if should_update and buffer:
                        messages = buffer[:]
                        buffer.clear()
                        last_update = current_time
                        
                        # 异步更新UI - 批量一次性插入
                        def update_ui():
                            if hasattr(self, 'progress_panel') and self.progress_panel:
                                # 一次性批量插入，减少UI重绘
                                combined_text = '\n'.join(messages)
                                try:
                                    self.progress_panel.log_text.configure(state="normal")
                                    self.progress_panel.log_text.insert("end", combined_text + '\n')
                                    # 限制日志行数（降低到50行）
                                    lines = int(self.progress_panel.log_text.index('end-1c').split('.')[0])
                                    if lines > 50:  # 100→50
                                        self.progress_panel.log_text.delete('1.0', f'{lines-50}.0')
                                    # 启用自动滚动但优化频率
                                    self.progress_panel.log_text.see("end")
                                    self.progress_panel.log_text.configure(state="disabled")
                                except:
                                    pass
                        
                        try:
                            # 使用after_idle优化UI响应
                            self.after_idle(update_ui)
                        except:
                            pass
                    
                    time.sleep(1.0)  # 降低轮询频率（0.5→1.0秒）
                    
                except Exception as e:
                    print(f"Log processor error: {e}")
                    time.sleep(1.0)
        
        # 启动后台日志处理线程
        log_thread = threading.Thread(target=process_logs, daemon=True)
        log_thread.start()
    
    def log(self, message: str):
        """记录日志（异步队列版 - 零卡顿）"""
        # 直接放入队列，不阻塞主线程
        try:
            self.log_queue.put_nowait(message)
        except:
            # 队列满时丢弃旧消息
            try:
                self.log_queue.get_nowait()
                self.log_queue.put_nowait(message)
            except:
                pass
    
    def quick_scan(self):
        """快速扫描（多线程）"""
        self.log("🔍 开始快速扫描...")
        self.clear_selection()
        
        thread = threading.Thread(target=self._quick_scan_thread, daemon=True)
        thread.start()
    
    def _quick_scan_thread(self):
        """快速扫描线程（实时进度）"""
        start_time = time.time()
        
        # 获取所有磁盘
        self.drives_data = self.scanner.get_all_drives()
        self.after(0, self.update_disk_display)
        
        # 快速扫描C盘文件夹
        self.log("📊 快速扫描C盘文件夹...")
        self.log("⏱️ 正在扫描，请稍候...")
        
        # 实时进度回调 - 显示所有进度
        scan_count = [0]
        def progress_callback(msg):
            scan_count[0] += 1
            # 显示所有进度，让用户看到扫描状态
            self.log(msg)
        
        c_analysis = self.engine.get_drive_quick_analysis(
            "C:\\",
            self.scanner.system_folders,
            progress_callback=progress_callback
        )
        self.drive_analyses['C:\\'] = c_analysis
        
        elapsed = int(time.time() - start_time)
        self.log(f"✓ 快速扫描完成！用时: {elapsed}秒")
        self.log("📝 说明：快速扫描仅获取根文件夹大小")
        self.log("💡 提示：展开文件夹时会扫描子文件夹（首次需要时间）")
        self.log("💡 建议：使用深度扫描一次性获取完整数据")
        
        # 更新C盘分析显示
        self.after(0, lambda: self.analysis_panel.update_analysis(c_analysis))
        
        # 提取可移动文件夹
        self._update_movable_folders(c_analysis)
    
    def deep_scan(self):
        """深度扫描（完整扫描所有文件）"""
        # 检查缓存
        cache_key = "deep_scan_C:\\"
        cached_data = self.cache.get(cache_key)
        
        if cached_data:
            cache_age = self.cache.get_cache_age(cache_key)
            age_minutes = cache_age // 60 if cache_age is not None else 0
            use_cache = messagebox.askyesno(
                "发现缓存",
                f"找到 {age_minutes} 分钟前的扫描结果。\n\n使用缓存数据？\n\n点击「否」将重新扫描"
            )
            
            if use_cache:
                self.log(f"📦 使用缓存数据（{age_minutes}分钟前）")
                self.drive_analyses['C:\\'] = cached_data
                self.after(0, lambda: self.analysis_panel.update_analysis(cached_data))
                
                # 提取可移动文件夹
                self._update_movable_folders(cached_data)
                return
        
        confirm = messagebox.askyesno(
            "深度扫描",
            "深度扫描会完整遍历所有文件，时间较长。\n\n"
            "特点：\n"
            "✓ 100%精确统计\n"
            "✓ 递归扫描所有子文件夹\n"
            "✓ 自动缓存结果（24小时）\n"
            "⏱️ 首次扫描需要 2-10 分钟\n\n"
            "💡 提示：请耐心等待，扫描进度会在日志中显示\n\n"
            "确定要开始吗？"
        )
        
        if not confirm:
            return
        
        # 清空日志并显示开始提示
        if self.progress_panel and hasattr(self.progress_panel, 'clear') and callable(getattr(self.progress_panel, 'clear', None)):
            self.progress_panel.clear()
        self.log("="*50)
        self.log("🔬 深度扫描模式")
        self.log("="*50)
        self.log("⚡ 使用 " + str(self.startup_workers) + " 个工作线程")
        self.log("💾 启用智能缓存系统")
        self.log("")
        self.clear_selection()
        
        thread = threading.Thread(target=self._deep_scan_thread, daemon=True)
        thread.start()
    
    def _deep_scan_thread(self):
        """深度扫描线程（优化等待体验）"""
        start_time = time.time()
        
        # 获取所有磁盘
        self.drives_data = self.scanner.get_all_drives()
        self.after(0, self.update_disk_display)
        
        # 深度扫描C盘 - 优化体验
        self.log("🔬 深度扫描启动...")
        self.log("💡 首次扫描会遍历所有子文件夹，请耐心等待")
        self.log("⏱️ 预计需要 2-10 分钟，取决于文件数量")
        self.log("⏳ 扫描进度会在下方显示，请关注日志")
        self.log("")  # 空行分隔
        
        # 创建优化的进度回调：显示详细进度
        self._scan_progress_count = 0
        self._last_update_time = time.time()
        
        def enhanced_callback(message):
            self._scan_progress_count += 1
            current_time = time.time()
            elapsed = current_time - start_time
            
            # 每5次或重要消息才更新
            should_update = (
                self._scan_progress_count % 5 == 0 or
                any(x in message for x in ['完成', '✓', '✗', '错误', '深度扫描进度'])
            )
            
            if should_update:
                # 添加进度信息
                if '深度扫描进度:' in message:
                    # 提取百分比
                    try:
                        percent_str = message.split('(')[0].split(':')[1].strip()
                        self.log(f"⏳ 进度: {percent_str} | 已用时: {int(elapsed)}秒")
                    except:
                        self.log(message)
                else:
                    self.log(message)
        
        # 使用并行引擎进行深度扫描（真正的极速扫描）
        c_analysis = self.scanner.get_drive_analysis(
            "C:\\", 
            progress_callback=enhanced_callback,
            use_parallel=True,  # 启用并行
            max_workers=self.startup_workers,  # 使用所有线程
            shared_engine=self.engine  # 传递共享引擎以共享缓存
        )
        self.drive_analyses['C:\\'] = c_analysis
        
        # 显示完成信息
        total_time = int(time.time() - start_time)
        self.log("")
        self.log(f"✅ 深度扫描完成！总用时: {total_time}秒")
        
        # 保存到缓存
        self.cache.set("deep_scan_C:\\", c_analysis)
        self.log("💾 扫描结果已缓存（24小时有效）")
        
        # 更新C盘分析显示
        self.after(0, lambda: self.analysis_panel.update_analysis(c_analysis))
        
        # 提取可移动文件夹（使用深度扫描的结果！）
        self._update_movable_folders(c_analysis, "深度扫描结果")
    
    def update_disk_display(self):
        """更新磁盘卡片显示"""
        for widget in self.disk_container.winfo_children():
            widget.destroy()
        
        for drive in self.drives_data:
            card = DriveCard(
                self.disk_container,
                drive,
                on_analyze=self.analyze_drive
            )
            card.pack(fill="x", pady=5)
        
        # 更新目标磁盘选项（允许所有磁盘）
        targets = [d['letter'] for d in self.drives_data]
        if targets:
            self.target_menu.configure(values=targets)
            # 默认选择非C盘，如果只有C盘则选择C盘
            default_target = next((d for d in targets if d != 'C:\\'), targets[0])
            self.target_var.set(default_target)
            self.selected_target_drive = default_target
    
    def analyze_drive(self, drive_letter: str):
        """分析指定磁盘"""
        self.log(f"🔍 开始分析 {drive_letter}...")
        
        def analyze_thread():
            # 创建优化的进度回调：减少日志更新频率
            progress_count = [0]  # 使用列表以在闭包中修改
            def optimized_callback(message):
                progress_count[0] += 1
                # 每3次或重要消息才更新
                if progress_count[0] % 3 == 0 or any(x in message for x in ['完成', '✓', '✗']):
                    self.log(message)
            
            analysis = self.engine.get_drive_quick_analysis(
                drive_letter,
                self.scanner.system_folders,
                progress_callback=optimized_callback
            )
            self.drive_analyses[drive_letter] = analysis
            self.after(0, lambda: self.analysis_panel.update_analysis(analysis))
        
        threading.Thread(target=analyze_thread, daemon=True).start()
    
    def update_folder_display(self):
        """更新文件夹列表（树形结构 + 搜索支持）"""
        for widget in self.folder_container.winfo_children():
            widget.destroy()
        
        self.folder_items = []
        
        if not self.folders_data:
            no_data = ctk.CTkLabel(
                self.folder_container,
                text="未找到可移动的文件夹",
                font=ctk.CTkFont(size=13),
                text_color="gray"
            )
            no_data.pack(pady=30)
            return
        
        # 只显示根级别文件夹（树形结构）
        root_folders = [f for f in self.folders_data if not f.get('parent') or f.get('parent') == '']
        
        # 限制显示数量：最多FOLDER_DISPLAY_LIMIT个
        display_limit = FOLDER_DISPLAY_LIMIT
        total_folders = len(root_folders)
        folders_to_display = root_folders[:display_limit]
        
        # 显示统计信息
        if total_folders > display_limit:
            info_label = ctk.CTkLabel(
                self.folder_container,
                text=f"📊 总共 {total_folders} 个根文件夹，显示前 {display_limit} 个最大的",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="orange"
            )
            info_label.pack(pady=5)
        
        for folder in folders_to_display:
            # 检查是否有子文件夹
            has_children = folder.get('has_children', False) or (folder.get('children') and len(folder.get('children', [])) > 0)
            
            # 为所有文件夹提供展开功能（即使当前没有缓存子文件夹）
            item = FolderItem(
                self.folder_container,
                folder,
                on_toggle=self.on_folder_toggle,
                format_size_func=self.scanner.format_size,
                on_expand=self.on_folder_expand  # 总是提供展开回调
            )
            item.pack(fill="x", pady=3)
            item.folder_data = folder  # 确保folder_data设置
            
            # 绑定右键菜单
            item.bind("<Button-3>", lambda e, f=folder: self.show_context_menu(e, f))
            
            self.folder_items.append(item)
    
    def show_context_menu(self, event, folder_data: dict):
        """显示右键菜单"""
        menu = self.create_context_menu(folder_data, event.widget)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def on_folder_toggle(self, folder: dict, selected: bool):
        """文件夹选择切换"""
        if selected and folder not in self.selected_folders:
            self.selected_folders.append(folder)
        elif not selected and folder in self.selected_folders:
            self.selected_folders.remove(folder)
        
        self.update_selection_display()
    
    def _on_search(self, query: str):
        """处理搜索（搜索面板回调）"""
        if not query:
            # 清空搜索，显示根文件夹
            self.update_folder_display()
            return
        
        # 展平所有文件夹（包括子文件夹）
        all_flat_folders = self._flatten_folders(self.folders_data)
        
        # 过滤匹配的文件夹
        matching_folders = filter_folders(all_flat_folders, query)
        
        # 清空显示
        for widget in self.folder_container.winfo_children():
            widget.destroy()
        
        # 显示搜索结果
        if not matching_folders:
            no_result = ctk.CTkLabel(
                self.folder_container,
                text=f"🔍 没有找到匹配 '{query}' 的文件夹",
                font=ctk.CTkFont(size=13),
                text_color="gray"
            )
            no_result.pack(pady=30)
            self.log(f"🔍 搜索 '{query}': 未找到匹配项")
            return
        
        # 限制搜索结果显示数量
        results_to_display = matching_folders[:FOLDER_DISPLAY_LIMIT]
        
        if len(matching_folders) > FOLDER_DISPLAY_LIMIT:
            info_label = ctk.CTkLabel(
                self.folder_container,
                text=f"🔍 找到 {len(matching_folders)} 个匹配项，显示前 {FOLDER_DISPLAY_LIMIT} 个",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="orange"
            )
            info_label.pack(pady=5)
        
        for folder in results_to_display:
            item = FolderItem(
                self.folder_container,
                folder,
                on_toggle=self.on_folder_toggle,
                format_size_func=self.scanner.format_size,
                on_expand=None  # 搜索结果不支持展开
            )
            item.pack(fill="x", pady=3)
        
        self.log(f"🔍 搜索 '{query}': 找到 {len(matching_folders)} 个匹配项")
    
    def _flatten_folders(self, folders: list) -> list:
        """展平文件夹列表（包括所有子文件夹）"""
        result = []
        for folder in folders:
            result.append(folder)
            if folder.get('children'):
                result.extend(self._flatten_folders(folder['children']))
        return result
    
    def on_folder_expand(self, folder: dict, folder_item):
        """展开文件夹，显示子项"""
        
        def scan_sub_folders():
            import time
            start_time = time.time()
            scan_count = [0]  # 使用列表以便在闭包中修改
            
            # 检查缓存
            has_cache = self.engine.cache and self.engine.cache.has_valid_cache(f"subfolder_list_{folder['path']}")
            
            if has_cache:
                self.log(f"📦 从缓存加载 {folder['name']} 的子文件夹...")
            else:
                self.log(f"🔍 正在扫描 {folder['name']} 的子文件夹...")
                self.log("⏳ 首次扫描需要一些时间，请稍候...")
            
            try:
                sub_folders = []
                for entry in os.scandir(folder['path']):
                    folder_name = entry.name
                    access_denied = False
                    scan_error = None
                    
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # 先测试访问权限
                            try:
                                list(os.scandir(entry.path))
                                can_access = True
                            except PermissionError:
                                can_access = False
                                access_denied = True
                                folder_name = f"🔒 {entry.name} (无法访问)"
                            except Exception as e:
                                can_access = False
                                scan_error = type(e).__name__
                                folder_name = f"⚠️ {entry.name} (错误: {scan_error})"
                            
                            # 如果可以访问，扫描大小
                            if can_access:
                                scan_count[0] += 1
                                # 每扫描5个文件夹显示一次进度
                                if scan_count[0] % 5 == 0 and not has_cache:
                                    elapsed = int(time.time() - start_time)
                                    self.log(f"  ⏳ 已扫描 {scan_count[0]} 个子文件夹，用时 {elapsed}秒...")
                                
                                size = self.engine.get_folder_size_parallel(entry.path, max_depth=None, use_cache=True, follow_symlinks=True)
                                if size == 0:
                                    # 真正的空文件夹
                                    folder_name = f"📂 {entry.name} (空)"
                            else:
                                size = 0
                            
                            sub_folders.append({
                                'name': folder_name,
                                'path': entry.path,
                                'size': size,
                                'is_system': access_denied or scan_error is not None,
                                'movable': size > 1 * 1024 * 1024 and not access_denied,
                                'has_children': size > 0,
                                'access_denied': access_denied,
                                'scan_error': scan_error
                            })
                    except Exception as e:
                        # 外层异常捕获
                        sub_folders.append({
                            'name': f"❌ {entry.name if hasattr(entry, 'name') else 'Unknown'} (严重错误)",
                            'path': entry.path if hasattr(entry, 'path') else '',
                            'size': 0,
                            'is_system': True,
                            'movable': False,
                            'has_children': False,
                            'access_denied': True,
                            'scan_error': type(e).__name__
                        })
                
                # 按大小排序
                sub_folders.sort(key=lambda x: x['size'], reverse=True)
                
                # 显示完成信息
                elapsed = int(time.time() - start_time)
                if has_cache:
                    self.log(f"✓ 从缓存加载完成！找到 {len(sub_folders)} 个子文件夹（用时: {elapsed}秒）")
                else:
                    self.log(f"✓ 扫描完成！找到 {len(sub_folders)} 个子文件夹（用时: {elapsed}秒）")
                    # 保存到缓存
                    if self.engine.cache:
                        self.engine.cache.set(f"subfolder_list_{folder['path']}", {
                            'folders': sub_folders,
                            'count': len(sub_folders)
                        })
                
                # 在UI线程中添加子项
                self.after(0, lambda: self._add_sub_folder_items(folder_item, sub_folders[:20]))
                
                if not sub_folders:
                    self.log(f"⚠️ 没有可访问的子文件夹（可能为空或需要管理员权限）")
            except Exception as e:
                error_msg = str(e)
                if "WinError 5" in error_msg or "拒绝访问" in error_msg:
                    self.log(f"🔒 无法访问：需要管理员权限或系统保护")
                else:
                    self.log(f"✗ 扫描失败: {error_msg}")
        
        # 后台线程扫描
        threading.Thread(target=scan_sub_folders, daemon=True).start()
    
    def _add_sub_folder_items(self, parent_item, sub_folders):
        """添加子文件夹项"""
        # 如果已经有子项，先清除
        if hasattr(parent_item, 'sub_items'):
            for item in parent_item.sub_items:
                item.destroy()
        
        parent_item.sub_items = []
        
        # 创建新的子项（所有级别都可以展开）
        for sub in sub_folders:
            sub_item = FolderItem(
                parent_item.master,
                sub,
                on_toggle=self.on_folder_toggle,
                format_size_func=self.scanner.format_size,
                on_expand=self.on_folder_expand,  # 子项也可以展开
                level=parent_item.level + 1
            )
            # 插入到父项后面
            sub_item.pack(fill="x", pady=2, after=parent_item)
            parent_item.sub_items.append(sub_item)
            self.folder_items.append(sub_item)
    
    def select_all(self):
        """全选（只选择当前显示的文件夹）"""
        if not hasattr(self, 'folder_items'):
            self.log("⚠️ folder_items不存在")
            return
        
        if not self.folder_items:
            self.log("⚠️ 没有可选择的文件夹，请先运行扫描")
            return
        
        self.log(f"🔍 开始全选，当前有 {len(self.folder_items)} 个文件夹项")
        
        # 从显示的items中提取folder数据
        self.selected_folders = []
        count = 0
        for item in self.folder_items[:SELECT_ALL_LIMIT]:
            if hasattr(item, 'folder_data') and hasattr(item, 'set_selected'):
                self.selected_folders.append(item.folder_data)
                item.set_selected(True)
                count += 1
            else:
                self.log(f"⚠️ 项 {type(item)} 缺少必要属性")
        
        self.update_selection_display()
        self.log(f"✓ 已选择 {count} 个文件夹")
    
    def clear_selection(self):
        """清空选择"""
        if not hasattr(self, 'folder_items'):
            return
        
        self.selected_folders = []
        for item in self.folder_items:
            if hasattr(item, 'set_selected'):
                item.set_selected(False)
        
        self.update_selection_display()
        self.log("✓ 已清空选择")
    
    def update_selection_display(self):
        """更新选择统计"""
        count = len(self.selected_folders)
        total_size = sum(f['size'] for f in self.selected_folders)
        total_gb = total_size / (1024**3)
        
        self.selection_label.configure(
            text=f"已选择: {count} 个 | 总大小: {total_gb:.2f} GB"
        )
        
        # 控制移动按钮
        if count > 0 and self.selected_target_drive:
            self.move_btn.configure(state="normal")
        else:
            self.move_btn.configure(state="disabled")
    
    def on_target_selected(self, choice: str):
        """目标磁盘选择"""
        self.selected_target_drive = choice
        self.update_selection_display()
        self.log(f"✓ 目标: {choice}")
    
    def start_batch_move(self):
        """开始批量移动"""
        if not self.selected_folders or not self.selected_target_drive:
            messagebox.showerror("错误", "请选择文件夹和目标磁盘！")
            return
        
        total_gb = sum(f['size'] for f in self.selected_folders) / (1024**3)
        
        confirm = messagebox.askyesno(
            "确认移动",
            f"确定移动 {len(self.selected_folders)} 个文件夹到 {self.selected_target_drive}？\n\n"
            f"总大小: {total_gb:.2f} GB\n"
            f"{'将创建符号链接' if self.link_var.get() else '不创建符号链接'}"
        )
        
        if not confirm:
            return
        
        self.move_btn.configure(state="disabled")
        
        # 确保 target_drive 不为 None
        target_drive = self.selected_target_drive if self.selected_target_drive else "C:\\"
        
        def move_thread():
            success = 0
            fail = 0
            
            for idx, folder in enumerate(self.selected_folders, 1):
                self.log(f"\n[{idx}/{len(self.selected_folders)}] {folder['name']}")
                
                result = self.mover.move_folder(
                    folder['path'],
                    target_drive,
                    progress_callback=self.log,
                    create_link=self.link_var.get()
                )
                
                if result['success']:
                    success += 1
                else:
                    fail += 1
            
            self.after(0, lambda: self.on_move_complete(success, fail))
        
        threading.Thread(target=move_thread, daemon=True).start()
    
    def on_move_complete(self, success: int, fail: int):
        """移动完成"""
        messagebox.showinfo(
            "完成",
            f"批量移动完成！\n\n成功: {success}\n失败: {fail}"
        )
        self.move_btn.configure(state="normal")
        self.clear_selection()
        self.quick_scan()
    
    def undo_move(self):
        """撤销移动"""
        history = self.mover.get_history()
        if not history:
            messagebox.showinfo("提示", "没有可恢复的操作")
            return
        
        last = history[-1]
        confirm = messagebox.askyesno(
            "确认恢复",
            f"恢复最后一次操作？\n\n{last.get('source', 'Unknown')}"
        )
        
        if confirm:
            result = self.mover.undo_last_move()
            if result['success']:
                messagebox.showinfo("成功", result['message'])
                self.quick_scan()
            else:
                messagebox.showerror("失败", result['error'])
    
    def bind_shortcuts(self):
        """绑定快捷键（C2增强功能）"""
        # Ctrl+A - 全选
        self.bind('<Control-a>', lambda e: self.select_all_folders())
        self.bind('<Control-A>', lambda e: self.select_all_folders())
        
        # Ctrl+D - 取消全选
        self.bind('<Control-d>', lambda e: self.deselect_all_folders())
        self.bind('<Control-D>', lambda e: self.deselect_all_folders())
        
        # F5 - 刷新扫描
        self.bind('<F5>', lambda e: self.quick_scan())
        
        # Ctrl+Z - 撤销操作
        self.bind('<Control-z>', lambda e: self.undo_move())
        self.bind('<Control-Z>', lambda e: self.undo_move())
        
        # Escape - 取消选择
        self.bind('<Escape>', lambda e: self.clear_selection())
    
    def select_all_folders(self):
        """全选所有文件夹（快捷键功能）"""
        if not self.folder_items:
            return
        
        for item in self.folder_items:
            item.set_selected(True)
            if item.folder_data not in self.selected_folders:
                self.selected_folders.append(item.folder_data)
        
        self.log(f"✅ 已全选 {len(self.selected_folders)} 个文件夹")
        self.update_selection_display()
    
    def deselect_all_folders(self):
        """取消全选（快捷键功能）"""
        self.clear_selection()
        self.log("❌ 已取消全选")
    
    def create_context_menu(self, folder_data: dict, widget=None):
        """创建右键菜单（C2增强功能）"""
        menu = tk.Menu(self, tearoff=0)
        
        # 单独移动此项
        menu.add_command(
            label="📦 单独移动此文件夹",
            command=lambda: self.move_single_folder(folder_data)
        )
        
        menu.add_separator()
        
        # 在资源管理器中打开
        menu.add_command(
            label="📂 在资源管理器中打开",
            command=lambda: self.open_in_explorer(folder_data['path'])
        )
        
        # 查看详细信息
        menu.add_command(
            label="ℹ️ 查看详细信息",
            command=lambda: self.show_folder_details(folder_data)
        )
        
        menu.add_separator()
        
        # 复制路径
        menu.add_command(
            label="📋 复制路径",
            command=lambda: self.copy_path_to_clipboard(folder_data['path'])
        )
        
        return menu
    
    def move_single_folder(self, folder_data: dict):
        """单独移动一个文件夹"""
        if not self.selected_target_drive:
            messagebox.showwarning("提示", "请先选择目标磁盘")
            return
        
        confirm = messagebox.askyesno(
            "确认移动",
            f"移动文件夹到 {self.selected_target_drive}？\n\n"
            f"文件夹: {folder_data['name']}\n"
            f"大小: {self.scanner.format_size(folder_data['size'])}"
        )
        
        if confirm:
            self.log(f"🚀 移动: {folder_data['name']}")
            target_drive = self.selected_target_drive if self.selected_target_drive else "C:\\"
            result = self.mover.move_folder(
                folder_data['path'],
                target_drive,
                progress_callback=self.log,
                create_link=self.link_var.get()
            )
            
            if result['success']:
                messagebox.showinfo("成功", f"移动完成！\n\n{result['message']}")
                self.quick_scan()
            else:
                messagebox.showerror("失败", result['error'])
    
    def open_in_explorer(self, path: str):
        """在Windows资源管理器中打开路径"""
        try:
            subprocess.Popen(f'explorer "{path}"')
            self.log(f"📂 已在资源管理器中打开: {path}")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开资源管理器: {str(e)}")
    
    def show_folder_details(self, folder_data: dict):
        """显示文件夹详细信息"""
        size_str = self.scanner.format_size(folder_data['size'])
        details = f"""
文件夹详细信息
{'='*40}

名称: {folder_data['name']}
路径: {folder_data['path']}
大小: {size_str}
系统文件夹: {'是' if folder_data.get('is_system') else '否'}
可移动: {'是' if folder_data.get('movable') else '否'}
        """
        messagebox.showinfo("文件夹详情", details.strip())
    
    def copy_path_to_clipboard(self, path: str):
        """复制路径到剪贴板"""
        self.clipboard_clear()
        self.clipboard_append(path)
        self.log(f"📋 已复制路径: {path}")
        messagebox.showinfo("成功", "路径已复制到剪贴板")
    
    def on_window_resize(self, event):
        """窗口大小变化处理（C4响应式布局）
        
        布局规则：
        - < 1200px: 单栏布局（仅显示主内容）
        - 1200-1600px: 双栏布局（主内容 + 右侧面板）
        - > 1600px: 三栏布局（左侧磁盘 + 主内容 + 右侧面板）
        """
        # 只处理主窗口的resize事件
        if event.widget != self:
            return
        
        width = event.width
        
        # 根据宽度确定布局模式
        if width < 1200:
            new_mode = "single-column"
        elif width < 1600:
            new_mode = "two-column"
        else:
            new_mode = "three-column"
        
        # 如果布局模式改变，记录日志
        if hasattr(self, 'current_layout_mode') and new_mode != self.current_layout_mode:
            self.current_layout_mode = new_mode
            # 暂时禁用动态布局切换，保持三栏布局
            # 完整的响应式切换需要重构UI，这里只记录
            # self.log(f"📐 布局模式: {new_mode} (宽度: {width}px)")
    
    def show_first_run_dialog(self):
        """显示首次启动欢迎弹窗"""
        # 检查是否已显示过
        flag_file = ".first_run_shown"
        if os.path.exists(flag_file):
            return  # 已显示过，直接返回
        
        # 调用dialogs模块的弹窗显示方法
        dialogs.show_dev_dialog(self, create_flag=True)
    
    def show_first_run_dialog_manual(self):
        """手动显示开发者弹窗（不检查标记）"""
        dialogs.show_dev_dialog(self, create_flag=False)
    
    def show_update_log(self):
        """显示更新记录弹窗"""
        dialogs.show_update_log(self)
    
    def on_closing(self):
        self.log_running = False
        if hasattr(self, 'engine'):
            self.engine.stop_scan()
        self.destroy()
def main():
    app = DiskMigrationApp()
    app.mainloop()

if __name__ == "__main__":
    main()
