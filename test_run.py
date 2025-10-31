#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试运行脚本 - 用于调试"""

import sys
import traceback

try:
    print("开始导入模块...")
    import customtkinter as ctk
    print("✓ customtkinter 导入成功")
    
    from theme_colors import DARK_THEME, LIGHT_THEME
    print("✓ theme_colors 导入成功")
    
    from animations import AnimationHelper, AnimatedProgressBar
    print("✓ animations 导入成功")
    
    from ui_components import GlassFrame, DriveCard, FolderItem, ProgressPanel, DriveAnalysisPanel
    print("✓ ui_components 导入成功")
    
    from scanner_engine import ScannerEngine
    print("✓ scanner_engine 导入成功")
    
    from scan_cache import ScanCache
    print("✓ scan_cache 导入成功")
    
    from disk_scanner import DiskScanner
    print("✓ disk_scanner 导入成功")
    
    from file_mover import FileMover
    print("✓ file_mover 导入成功")
    
    print("\n所有模块导入成功！")
    print("\n尝试启动主程序...")
    
    from main import DiskMigrationApp
    print("✓ main 导入成功")
    
    print("\n创建应用程序实例...")
    app = DiskMigrationApp()
    print("✓ 应用程序创建成功")
    
    print("\n启动GUI...")
    app.mainloop()
    
except Exception as e:
    print(f"\n❌ 错误: {type(e).__name__}")
    print(f"详细信息: {str(e)}")
    print("\n完整堆栈跟踪:")
    traceback.print_exc()
    sys.exit(1)
