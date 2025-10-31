import customtkinter as ctk
from tkinter import messagebox
import threading
import os
from queue import Queue
from disk_scanner import DiskScanner
from file_mover import FileMover
from scanner_engine import ScannerEngine
from ui_components import GlassFrame, DriveCard, FolderItem, ProgressPanel, DriveAnalysisPanel
from scan_cache import ScanCache

# 设置外观
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class DiskMigrationApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 核心模块
        self.scanner = DiskScanner()
        self.mover = FileMover()
        self.cache = ScanCache(expire_hours=24)  # 24小时缓存
        
        # 根据CPU核心数动态设置线程数（智能自适应）
        cpu_count = os.cpu_count() or 4
        # 智能线程数：根据CPU核心数自动调整，无上限
        # 公式：核心数 × 2，最少8个（让CPU自己决定性能上限）
        optimal_workers = max(cpu_count * 2, 8)
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
        
        # 显示启动信息
        self.log(f"⚡ 已启用 {self.startup_workers} 线程并行扫描")
        self.log("💡 快捷键: Ctrl+A全选 | Ctrl+D取消 | F5刷新 | Ctrl+Z撤销")
        
        # 首次启动欢迎弹窗
        self.show_first_run_dialog()
        
        # 自动开始扫描
        self.after(100, self.quick_scan)
    
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
        
        refresh_btn = ctk.CTkButton(
            btn_container,
            text="🔄 快速扫描",
            command=self.quick_scan,
            width=120,
            height=38,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=10
        )
        refresh_btn.grid(row=0, column=0, padx=3)
        
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
        deep_scan_btn.grid(row=0, column=1, padx=3)
        
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
        restore_btn.grid(row=0, column=2, padx=3)
        
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
        
        # 中栏：可移动文件夹
        middle_column = ctk.CTkFrame(main_container, fg_color="transparent")
        middle_column.pack(side="left", fill="both", expand=True, padx=8)
        
        # 文件夹标题和控制
        folder_header = GlassFrame(middle_column, height=60, corner_radius=10)
        folder_header.pack(fill="x", pady=(0, 10))
        folder_header.pack_propagate(False)
        
        folder_title = ctk.CTkLabel(
            folder_header,
            text="📁 可移动文件夹（多选）",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        folder_title.pack(side="left", padx=15)
        
        # 选择按钮
        btn_frame = ctk.CTkFrame(folder_header, fg_color="transparent")
        btn_frame.pack(side="right", padx=15)
        
        select_all_btn = ctk.CTkButton(
            btn_frame,
            text="☑ 全选",
            command=self.select_all,
            width=75,
            height=32,
            corner_radius=8
        )
        select_all_btn.pack(side="left", padx=3)
        
        clear_btn = ctk.CTkButton(
            btn_frame,
            text="☐ 清空",
            command=self.clear_selection,
            width=75,
            height=32,
            corner_radius=8
        )
        clear_btn.pack(side="left", padx=3)
        
        # 文件夹列表
        self.folder_container = ctk.CTkScrollableFrame(middle_column, fg_color="transparent")
        self.folder_container.pack(fill="both", expand=True, pady=(0, 10))
        
        # 选中统计
        self.selection_label = ctk.CTkLabel(
            middle_column,
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
        """启动异步日志处理器（后台线程 - 极致优化版）"""
        def process_logs():
            import time
            buffer = []
            last_update = time.time()
            
            while self.log_running:
                try:
                    # 非阻塞获取日志
                    while not self.log_queue.empty() and len(buffer) < 50:
                        msg = self.log_queue.get_nowait()
                        buffer.append(msg)
                    
                    # 每1秒或缓冲区满时更新UI（降低频率减少卡顿）
                    current_time = time.time()
                    should_update = (
                        len(buffer) >= 50 or
                        (buffer and current_time - last_update >= 1.0)
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
                                    # 限制日志行数
                                    lines = int(self.progress_panel.log_text.index('end-1c').split('.')[0])
                                    if lines > 200:
                                        self.progress_panel.log_text.delete('1.0', f'{lines-200}.0')
                                    # 降低滚动频率
                                    if lines % 10 == 0:
                                        self.progress_panel.log_text.see("end")
                                    self.progress_panel.log_text.configure(state="disabled")
                                except:
                                    pass
                        
                        try:
                            self.after(0, update_ui)
                        except:
                            pass
                    
                    time.sleep(0.2)  # 降低CPU使用
                    
                except Exception as e:
                    print(f"Log processor error: {e}")
                    time.sleep(0.5)
        
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
        import time
        start_time = time.time()
        
        # 获取所有磁盘
        self.drives_data = self.scanner.get_all_drives()
        self.after(0, self.update_disk_display)
        
        # 快速扫描C盘文件夹
        self.log("📊 快速扫描C盘文件夹...")
        self.log("⏱️ 正在扫描，请稍候...")
        
        # 实时进度回调
        scan_count = [0]
        def progress_callback(msg):
            scan_count[0] += 1
            # 显示所有进度（快速扫描不过滤）
            self.log(msg)
        
        c_analysis = self.engine.get_drive_quick_analysis(
            "C:\\",
            self.scanner.system_folders,
            progress_callback=progress_callback
        )
        self.drive_analyses['C:\\'] = c_analysis
        
        elapsed = int(time.time() - start_time)
        self.log(f"✓ 快速扫描完成！用时: {elapsed}秒")
        
        # 更新C盘分析显示
        self.after(0, lambda: self.analysis_panel.update_analysis(c_analysis))
        
        # 提取可移动文件夹
        self.folders_data = [f for f in c_analysis['folders'] if f.get('movable', False)]
        self.after(0, self.update_folder_display)
        
        self.log(f"✓ 找到 {len(self.folders_data)} 个可移动文件夹")
    
    def deep_scan(self):
        """深度扫描（完整扫描所有文件）"""
        # 检查缓存
        cache_key = "deep_scan_C:\\"
        cached_data = self.cache.get(cache_key)
        
        if cached_data:
            age_minutes = self.cache.get_cache_age(cache_key) // 60
            use_cache = messagebox.askyesno(
                "发现缓存",
                f"找到 {age_minutes} 分钟前的扫描结果。\n\n使用缓存数据？\n\n点击「否」将重新扫描"
            )
            
            if use_cache:
                self.log(f"📦 使用缓存数据（{age_minutes}分钟前）")
                self.c_drive_analysis = cached_data
                self.drive_analyses['C:\\'] = cached_data
                self.after(0, lambda: self.analysis_panel.update_analysis(cached_data))
                
                # 重新计算movable字段（防止旧缓存没有movable字段）
                all_folders = cached_data.get('folders', [])
                for folder in all_folders:
                    if 'movable' not in folder:
                        folder['movable'] = not folder.get('is_system', False) and folder.get('size', 0) > 10 * 1024 * 1024
                
                self.folders_data = [f for f in all_folders if f.get('movable', False)]
                self.after(0, self.update_folder_display)
                self.log(f"✓ 找到 {len(self.folders_data)} 个可移动文件夹")
                return
        
        confirm = messagebox.askyesno(
            "深度扫描",
            "深度扫描会完整遍历所有文件，时间较长。\n\n"
            "特点：\n"
            "✓ 100%精确统计\n"
            "✓ 自动缓存结果（24小时）\n"
            "⏱️ 预计需要 1-5 分钟\n\n"
            "确定要开始吗？"
        )
        
        if not confirm:
            return
        
        # 清空日志并显示开始提示
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
        import time
        start_time = time.time()
        
        # 获取所有磁盘
        self.drives_data = self.scanner.get_all_drives()
        self.after(0, self.update_disk_display)
        
        # 深度扫描C盘 - 优化体验
        self.log("🔬 深度扫描启动...")
        self.log("⏱️ 预计需要 1-5 分钟，取决于文件数量")
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
            max_workers=self.startup_workers  # 使用所有线程
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
        all_folders = c_analysis.get('folders', [])
        # 确保有movable字段
        for folder in all_folders:
            if 'movable' not in folder:
                folder['movable'] = not folder.get('is_system', False) and folder.get('size', 0) > 10 * 1024 * 1024
        
        self.folders_data = [f for f in all_folders if f.get('movable', False)]
        self.after(0, self.update_folder_display)
        
        self.log(f"✓ 找到 {len(self.folders_data)} 个可移动文件夹（深度扫描结果）")
    
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
        """更新文件夹列表"""
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
        
        for folder in self.folders_data[:100]:  # 限制100个
            item = FolderItem(
                self.folder_container,
                folder,
                on_toggle=self.on_folder_toggle,
                format_size_func=self.scanner.format_size,
                on_expand=self.on_folder_expand
            )
            item.pack(fill="x", pady=3)
            
            # 绑定右键菜单（C2增强）
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
    
    def on_folder_expand(self, folder: dict, folder_item):
        """展开文件夹，显示子项"""
        self.log(f"正在扫描 {folder['name']} 的子文件夹...")
        
        def scan_sub_folders():
            try:
                sub_folders = []
                for entry in os.scandir(folder['path']):
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            size = self.engine.get_folder_size_quick(entry.path, max_depth=1)
                            sub_folders.append({
                                'name': entry.name,
                                'path': entry.path,
                                'size': size,
                                'is_system': False,
                                'movable': size > 1 * 1024 * 1024,  # >1MB就可以移动
                                'has_children': True  # 可以继续展开
                            })
                    except (PermissionError, OSError):
                        continue
                
                # 按大小排序
                sub_folders.sort(key=lambda x: x['size'], reverse=True)
                
                # 在UI线程中添加子项
                self.after(0, lambda: self._add_sub_folder_items(folder_item, sub_folders[:20]))
                self.log(f"✓ 找到 {len(sub_folders)} 个子文件夹")
            except Exception as e:
                self.log(f"✗ 扫描失败: {str(e)}")
        
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
        """全选"""
        self.selected_folders = self.folders_data[:100].copy()
        for item in self.folder_items:
            item.set_selected(True)
        self.update_selection_display()
    
    def clear_selection(self):
        """清空选择"""
        self.selected_folders = []
        for item in self.folder_items:
            item.set_selected(False)
        self.update_selection_display()
    
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
        
        def move_thread():
            success = 0
            fail = 0
            
            for idx, folder in enumerate(self.selected_folders, 1):
                self.log(f"\n[{idx}/{len(self.selected_folders)}] {folder['name']}")
                
                result = self.mover.move_folder(
                    folder['path'],
                    self.selected_target_drive,
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
        self.update_move_button_state()
    
    def deselect_all_folders(self):
        """取消全选（快捷键功能）"""
        for item in self.folder_items:
            item.set_selected(False)
        
        self.selected_folders.clear()
        self.log("❌ 已取消全选")
        self.update_move_button_state()
    
    def create_context_menu(self, folder_data: dict, widget):
        """创建右键菜单（C2增强功能）"""
        import tkinter as tk
        
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
            result = self.mover.move_folder(
                folder_data['path'],
                self.selected_target_drive,
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
        import subprocess
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
    
    def adjust_font_sizes(self, width: int):
        """根据窗口宽度调整字体大小（C4响应式）
        
        Args:
            width: 窗口宽度
        """
        # 根据宽度调整字体
        if width < 1200:
            title_size = 20
            subtitle_size = 10
            button_size = 11
        elif width < 1600:
            title_size = 24
            subtitle_size = 11
            button_size = 12
        else:
            title_size = 26
            subtitle_size = 11
            button_size = 12
        
        # 这里可以动态调整字体，但需要保存所有控件引用
        # 简化实现：仅在下次UI重建时生效
        pass
    
    def get_responsive_padding(self, width: int) -> int:
        """获取响应式内边距（C4响应式）
        
        Args:
            width: 窗口宽度
        
        Returns:
            内边距像素值
        """
        if width < 1200:
            return 10
        elif width < 1600:
            return 15
        else:
            return 20
    
    def show_first_run_dialog(self):
        """显示首次启动欢迎弹窗"""
        # 检查是否已显示过
        flag_file = ".first_run_shown"
        if os.path.exists(flag_file):
            return  # 已显示过，直接返回
        
        # 创建自定义弹窗
        dialog = ctk.CTkToplevel(self)
        dialog.title("欢迎使用 - 磁盘迁移工具 Pro")
        dialog.geometry("720x750")
        dialog.resizable(False, False)
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (720 // 2)
        y = (dialog.winfo_screenheight() // 2) - (750 // 2)
        dialog.geometry(f"720x750+{x}+{y}")
        
        # 设置为模态对话框
        dialog.transient(self)
        dialog.grab_set()
        
        # 处理关闭事件（只有点击X时才创建标记文件）
        def on_closing():
            try:
                with open(flag_file, 'w') as f:
                    f.write("shown")
            except:
                pass
            dialog.destroy()
        
        dialog.protocol("WM_DELETE_WINDOW", on_closing)
        
        # 标题
        title_label = ctk.CTkLabel(
            dialog,
            text="💾 磁盘迁移工具 Pro",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.pack(pady=(20, 5))
        
        subtitle_label = ctk.CTkLabel(
            dialog,
            text="欢迎使用！",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        subtitle_label.pack(pady=(0, 10))
        
        # 开发者信息容器（横向三列布局）
        info_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        info_frame.pack(pady=5, padx=50, fill="x")
        
        # 第一列：开发者信息
        dev_col = ctk.CTkFrame(info_frame, fg_color="transparent")
        dev_col.pack(side="left", fill="both", expand=True, padx=5)
        
        dev_label = ctk.CTkLabel(
            dev_col,
            text="🧑‍💻 开发者",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        dev_label.pack(pady=(0, 5))
        
        dev_info = ctk.CTkLabel(
            dev_col,
            text="wan",
            font=ctk.CTkFont(size=12)
        )
        dev_info.pack()
        
        # 第二列：联系方式
        contact_col = ctk.CTkFrame(info_frame, fg_color="transparent")
        contact_col.pack(side="left", fill="both", expand=True, padx=5)
        
        contact_label = ctk.CTkLabel(
            contact_col,
            text="📧 联系方式",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        contact_label.pack(pady=(0, 5))
        
        email_label = ctk.CTkLabel(
            contact_col,
            text="263257193@qq.com",
            font=ctk.CTkFont(size=11)
        )
        email_label.pack()
        
        # 第三列：开源项目
        github_col = ctk.CTkFrame(info_frame, fg_color="transparent")
        github_col.pack(side="left", fill="both", expand=True, padx=5)
        
        github_label = ctk.CTkLabel(
            github_col,
            text="🌟 开源项目",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        github_label.pack(pady=(0, 5))
        
        # GitHub链接按钮
        def open_github():
            import webbrowser
            webbrowser.open("https://github.com/bjfwan/windows-disk-tool")
        
        github_btn = ctk.CTkButton(
            github_col,
            text="访问GitHub",
            command=open_github,
            width=140,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("blue", "darkblue")
        )
        github_btn.pack()
        
        # 赞助信息容器（独立区域）
        sponsor_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        sponsor_frame.pack(pady=12, padx=50, fill="both", expand=True)
        
        sponsor_label = ctk.CTkLabel(
            sponsor_frame,
            text="💖 支持开发",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        sponsor_label.pack(pady=(0, 5))
        
        sponsor_info = ctk.CTkLabel(
            sponsor_frame,
            text="如果这个工具帮到了你，欢迎支持开发者！",
            font=ctk.CTkFont(size=13)
        )
        sponsor_info.pack(pady=(0, 8))
        
        # 收款码图片显示 - 居中对称布局
        qr_frame = ctk.CTkFrame(sponsor_frame, fg_color="transparent")
        qr_frame.pack(pady=5)
        
        try:
            from PIL import Image
            
            # 微信收款码 - 竖向矩形 3:4 比例
            if os.path.exists("wechat.jpg"):
                wechat_img = Image.open("wechat.jpg")
                wechat_img = wechat_img.resize((210, 280), Image.Resampling.LANCZOS)
                wechat_photo = ctk.CTkImage(light_image=wechat_img, dark_image=wechat_img, size=(210, 280))
                
                wechat_container = ctk.CTkFrame(qr_frame, fg_color="transparent")
                wechat_container.pack(side="left", padx=20)
                
                wechat_label = ctk.CTkLabel(wechat_container, image=wechat_photo, text="")
                wechat_label.pack()
                
                wechat_text = ctk.CTkLabel(
                    wechat_container, 
                    text="微信赞赏", 
                    font=ctk.CTkFont(size=15, weight="bold")
                )
                wechat_text.pack(pady=(10, 0))
            
            # 支付宝收款码 - 竖向矩形 3:4 比例
            if os.path.exists("apliy.jpg"):
                alipay_img = Image.open("apliy.jpg")
                alipay_img = alipay_img.resize((210, 280), Image.Resampling.LANCZOS)
                alipay_photo = ctk.CTkImage(light_image=alipay_img, dark_image=alipay_img, size=(210, 280))
                
                alipay_container = ctk.CTkFrame(qr_frame, fg_color="transparent")
                alipay_container.pack(side="left", padx=20)
                
                alipay_label = ctk.CTkLabel(alipay_container, image=alipay_photo, text="")
                alipay_label.pack()
                
                alipay_text = ctk.CTkLabel(
                    alipay_container, 
                    text="支付宝打赏", 
                    font=ctk.CTkFont(size=15, weight="bold")
                )
                alipay_text.pack(pady=(10, 0))
        
        except Exception as e:
            # 如果图片加载失败，显示文字说明
            fallback_label = ctk.CTkLabel(
                sponsor_frame,
                text="收款码图片：wechat.jpg | apliy.jpg",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            fallback_label.pack(pady=5)
        
        # 底部提示
        separator = ctk.CTkFrame(dialog, height=1, fg_color="gray30")
        separator.pack(fill="x", padx=50, pady=(10, 8))
        
        tip_label = ctk.CTkLabel(
            dialog,
            text="💡 此弹窗仅在首次启动时显示，关闭窗口即可开始使用",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        tip_label.pack(pady=(5, 15))

def main():
    app = DiskMigrationApp()
    app.mainloop()

if __name__ == "__main__":
    main()
