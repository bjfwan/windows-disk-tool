import os
import psutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import ctypes

class DiskScanner:
    def __init__(self):
        self.system_folders = {
            'Windows', 'Program Files', 'Program Files (x86)', 
            'ProgramData', 'System Volume Information', '$Recycle.Bin'
        }
    
    def get_all_drives(self) -> List[Dict]:
        """获取所有磁盘驱动器信息"""
        drives = []
        for partition in psutil.disk_partitions():
            if 'cdrom' in partition.opts or partition.fstype == '':
                continue
            
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                drives.append({
                    'letter': partition.mountpoint,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent
                })
            except:
                continue
        
        return drives
    
    def format_size(self, bytes_size: int) -> str:
        """格式化文件大小"""
        size_float = float(bytes_size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_float < 1024.0:
                return f"{size_float:.2f} {unit}"
            size_float /= 1024.0
        return f"{size_float:.2f} PB"
    
    def is_admin(self) -> bool:
        """检查是否具有管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def get_folder_size_fast(self, path: str, progress_callback=None, follow_symlinks: bool = True) -> int:
        """快速计算文件夹大小（完整扫描 - 性能优化版）
        
        优化点：
        1. 批量收集entry，减少系统调用
        2. 缓存stat结果
        3. 智能进度报告（仅关键节点）
        4. 支持扫描符号链接（默认启用）
        """
        total_size = 0
        file_count = 0
        folder_count = 0
        last_report_count = 0
        
        try:
            for dirpath, dirnames, filenames in os.walk(path, followlinks=follow_symlinks):
                # 批量处理文件（减少系统调用）
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        # 使用os.path.getsize而非stat（更快）
                        total_size += os.path.getsize(filepath)
                        file_count += 1
                    except (OSError, PermissionError):
                        continue
                
                folder_count += 1
                
                # 智能进度报告：每扫描100个文件夹才报告一次
                if progress_callback and folder_count - last_report_count >= 100:
                    # 不再频繁报告，减少UI压力
                    last_report_count = folder_count
                    
        except (OSError, PermissionError):
            pass
        
        return total_size
    
    def get_drive_analysis(self, drive_letter: str, progress_callback=None, use_parallel=True, max_workers=None, shared_engine=None) -> Dict:
        """获取指定磁盘的完整容量分析
        
        Args:
            drive_letter: 驱动器盘符
            progress_callback: 进度回调函数
            use_parallel: 是否并行扫描
            max_workers: 最大工作线程数
            shared_engine: 共享的扫描引擎实例（用于共享缓存）
        """
        drive = drive_letter if drive_letter.endswith("\\") else drive_letter + "\\"
        
        # 智能动态设置线程数（根据磁盘类型）
        if max_workers is None:
            cpu_count = os.cpu_count() or 4
            try:
                from disk_detector import get_optimal_workers
                max_workers = get_optimal_workers(drive, cpu_count)
                if progress_callback:
                    from disk_detector import get_disk_type
                    disk_type = get_disk_type(drive)
                    progress_callback(f"📊 检测到{drive}为{disk_type}，使用{max_workers}线程")
            except:
                # 如果检测失败，使用默认策略
                max_workers = min(max(cpu_count * 2, 8), 32)
        
        analysis = {
            'total_size': 0,
            'used_size': 0,
            'free_size': 0,
            'folders': [],
            'top_folders': []
        }
        
        try:
            usage = psutil.disk_usage(drive)
            analysis['total_size'] = usage.total
            analysis['used_size'] = usage.used
            analysis['free_size'] = usage.free
            analysis['percent'] = usage.percent
            analysis['drive_letter'] = drive
            
            if progress_callback:
                progress_callback(f"开始扫描 {drive}...")
            
            # 扫描所有根目录文件夹和文件
            folders = []
            root_files_size = 0
            
            if use_parallel:
                # 多线程并行扫描
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                # 收集文件夹列表（批量处理）
                folder_list = []
                for entry in os.scandir(drive):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            # 缓存stat结果，避免重复调用
                            stat_info = entry.stat()
                            root_files_size += stat_info.st_size
                        elif entry.is_dir(follow_symlinks=False):
                            folder_list.append((entry.path, entry.name, entry.name in self.system_folders))
                    except (OSError, PermissionError):
                        continue
                
                # 使用共享引擎或创建新引擎
                if shared_engine:
                    engine = shared_engine
                else:
                    from scanner_engine import ScannerEngine
                    from scan_cache import ScanCache
                    cache = ScanCache()
                    engine = ScannerEngine(max_workers=max_workers, cache=cache)
                
                # 定义扫描函数（完整深度扫描 - 包含子文件夹详细信息）
                def scan_one_folder(path, name, is_sys, parent_path=""):
                    # 使用共享引擎扫描父文件夹总大小
                    size = engine.get_folder_size_parallel(path, max_depth=None, use_cache=True, follow_symlinks=True)
                    folder_info = {
                        'name': name,
                        'path': path,
                        'size': size,
                        'is_system': is_sys,
                        'percent_of_disk': (size / usage.used) * 100 if usage.used > 0 else 0,
                        'percent_of_total': (size / usage.total) * 100 if usage.total > 0 else 0,
                        'parent': parent_path
                    }
                    
                    # 深度扫描：获取子文件夹详细列表（利用缓存优化）
                    sub_folders = []
                    try:
                        entries = list(os.scandir(path))
                        
                        for entry in entries:
                            if not entry.is_dir(follow_symlinks=False):
                                continue
                            
                            folder_name = entry.name
                            is_symlink = entry.is_symlink()
                            
                            try:
                                # 使用缓存扫描子文件夹（关键优化点）
                                sub_size = engine.get_folder_size_parallel(
                                    entry.path, 
                                    max_depth=None,
                                    use_cache=True,  # 利用父文件夹扫描时的缓存
                                    follow_symlinks=True
                                )
                                
                                if sub_size == 0:
                                    if is_symlink:
                                        folder_name = f"🔗 {entry.name} (符号链接-空)"
                                    else:
                                        folder_name = f"📂 {entry.name} (空)"
                                elif is_symlink:
                                    folder_name = f"🔗 {entry.name}"
                                    
                                sub_folders.append({
                                    'name': folder_name,
                                    'path': entry.path,
                                    'size': sub_size,
                                    'is_system': False,
                                    'is_symlink': is_symlink,
                                    'percent_of_disk': (sub_size / usage.used) * 100 if usage.used > 0 else 0,
                                    'percent_of_total': (sub_size / usage.total) * 100 if usage.total > 0 else 0,
                                    'parent': path,
                                    'movable': sub_size > 1 * 1024 * 1024
                                })
                            except (PermissionError, OSError):
                                # 无权限的文件夹
                                sub_folders.append({
                                    'name': f"🔒 {entry.name} (无法访问)",
                                    'path': entry.path,
                                    'size': 0,
                                    'is_system': True,
                                    'is_symlink': False,
                                    'percent_of_disk': 0,
                                    'percent_of_total': 0,
                                    'parent': path,
                                    'movable': False,
                                    'access_denied': True
                                })
                    except (OSError, PermissionError):
                        pass
                    
                    return folder_info, sub_folders
                
                # 并行扫描
                import time as time_module
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(scan_one_folder, path, name, is_sys): (name, time_module.time()) for path, name, is_sys in folder_list}
                    
                    completed = 0
                    total = len(futures)
                    last_reported_percent = 0
                    scan_start_time = time_module.time()
                    
                    for future in as_completed(futures):
                        folder_name, start_time = futures[future]
                        completed += 1
                        elapsed = int(time_module.time() - start_time)
                        total_elapsed = int(time_module.time() - scan_start_time)
                        
                        try:
                            folder_info, sub_folders = future.result()
                            # 添加movable字段
                            folder_info['movable'] = not folder_info['is_system'] and folder_info['size'] > 1 * 1024 * 1024
                            folders.append(folder_info)
                            
                            # 子文件夹作为children存储，不直接添加到根列表
                            folder_info['children'] = sub_folders
                            folder_info['has_children'] = len(sub_folders) > 0
                            
                            # 实时显示每个文件夹的完成情况
                            current_percent = int((completed / total) * 100)
                            size_mb = folder_info['size'] / (1024 * 1024)
                            
                            if progress_callback:
                                if elapsed > 3:  # 扫描时间超过3秒的文件夹特别提示
                                    progress_callback(f"⏳ 进度: {current_percent}% ({completed}/{total}) | ✓ {folder_name} ({size_mb:.1f}MB, 用时{elapsed}秒) | 总用时: {total_elapsed}秒")
                                elif current_percent >= last_reported_percent + 10:
                                    progress_callback(f"⏳ 进度: {current_percent}% ({completed}/{total}) | 总用时: {total_elapsed}秒")
                                    last_reported_percent = current_percent
                        
                        except Exception as e:
                            # 记录错误但继续
                            if progress_callback:
                                progress_callback(f"⚠️ 扫描失败: {folder_name} - {type(e).__name__}: {str(e)[:50]}")
                            completed += 1  # 仍然计入进度
            else:
                # 顺序扫描（原逻辑）
                folder_count = 0
                for entry in os.scandir(drive):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            root_files_size += entry.stat().st_size
                        elif entry.is_dir(follow_symlinks=False):
                            folder_name = entry.name
                            is_system = folder_name in self.system_folders
                            
                            folder_count += 1
                            if progress_callback:
                                progress_callback(f"扫描 {drive} 第 {folder_count} 个文件夹: {folder_name}")
                            
                            size = self.get_folder_size_fast(entry.path, progress_callback, follow_symlinks=True)
                            
                            if progress_callback:
                                progress_callback(f"✓ {folder_name}: {self.format_size(size)}")
                            
                            folder_info = {
                                'name': folder_name,
                                'path': entry.path,
                                'size': size,
                                'is_system': is_system,
                                'movable': not is_system and size > 1 * 1024 * 1024,  # 降低到1MB
                                'percent_of_disk': (size / usage.used) * 100 if usage.used > 0 else 0,
                                'percent_of_total': (size / usage.total) * 100 if usage.total > 0 else 0
                            }
                            folders.append(folder_info)
                            
                            # 顺序扫描也添加子文件夹（保持一致）
                            try:
                                for sub_entry in os.scandir(entry.path):
                                    try:
                                        if sub_entry.is_dir(follow_symlinks=False):
                                            sub_size = self.get_folder_size_fast(sub_entry.path)
                                            if sub_size > 1 * 1024 * 1024:
                                                folders.append({
                                                    'name': sub_entry.name,
                                                    'path': sub_entry.path,
                                                    'size': sub_size,
                                                    'is_system': False,
                                                    'movable': sub_size > 1 * 1024 * 1024,
                                                    'percent_of_disk': (sub_size / usage.used) * 100 if usage.used > 0 else 0,
                                                    'percent_of_total': (sub_size / usage.total) * 100 if usage.total > 0 else 0,
                                                    'parent': entry.path
                                                })
                                    except (OSError, PermissionError):
                                        continue
                            except (OSError, PermissionError):
                                pass
                    except (OSError, PermissionError):
                        continue
            
            # 按大小排序
            folders.sort(key=lambda x: x['size'], reverse=True)
            
            # 计算已统计的总大小
            scanned_total = sum(f['size'] for f in folders) + root_files_size
            
            # 计算其他/未统计的空间
            other_size = max(0, usage.used - scanned_total)
            
            if other_size > 100 * 1024 * 1024:  # 大于100MB才显示
                folders.append({
                    'name': '其他文件（系统、隐藏文件等）',
                    'path': 'N/A',
                    'size': other_size,
                    'is_system': True,
                    'percent_of_disk': (other_size / usage.used) * 100 if usage.used > 0 else 0,
                    'percent_of_total': (other_size / usage.total) * 100 if usage.total > 0 else 0
                })
            
            if root_files_size > 0:
                folders.append({
                    'name': f'{drive}根目录文件',
                    'path': drive,
                    'size': root_files_size,
                    'is_system': False,
                    'percent_of_disk': (root_files_size / usage.used) * 100 if usage.used > 0 else 0,
                    'percent_of_total': (root_files_size / usage.total) * 100 if usage.total > 0 else 0
                })
            
            # 重新排序
            folders.sort(key=lambda x: x['size'], reverse=True)
            
            analysis['folders'] = folders
            analysis['top_folders'] = folders[:15]  # 增加到前15个
            analysis['scanned_total'] = scanned_total
            analysis['other_size'] = other_size
            
        except Exception as e:
            print(f"分析错误: {e}")
        
        return analysis
    
    def get_c_drive_analysis(self, progress_callback=None) -> Dict:
        """获取C盘完整容量分析（兼容方法）"""
        return self.get_drive_analysis("C:\\", progress_callback)
