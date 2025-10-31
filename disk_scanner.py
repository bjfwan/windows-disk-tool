import os
import psutil
from pathlib import Path
from typing import Dict, List, Tuple
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
    
    def get_folder_size(self, path: str, max_depth: int = None, current_depth: int = 0) -> int:
        """计算文件夹大小（支持无限深度）
        
        Args:
            path: 文件夹路径
            max_depth: 最大深度限制（None表示无限深度）
            current_depth: 当前深度
        """
        total_size = 0
        
        # 如果达到深度限制，返回当前结果
        if max_depth is not None and current_depth >= max_depth:
            return total_size
        
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        # 无限深度递归（max_depth=None）
                        total_size += self.get_folder_size(entry.path, max_depth, current_depth + 1)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        
        return total_size
    
    def scan_c_drive_folders(self, max_depth: int = None) -> List[Dict]:
        """扫描C盘根目录的文件夹（支持无限深度）
        
        Args:
            max_depth: 最大深度限制（None表示无限深度，建议快速扫描时设为2）
        """
        c_drive = "C:\\"
        folders = []
        
        try:
            for entry in os.scandir(c_drive):
                if not entry.is_dir(follow_symlinks=False):
                    continue
                
                folder_name = entry.name
                
                # 标记系统关键文件夹
                is_system = folder_name in self.system_folders
                
                # 计算文件夹大小（无限深度）
                size = self.get_folder_size(entry.path, max_depth=max_depth)
                
                folders.append({
                    'name': folder_name,
                    'path': entry.path,
                    'size': size,
                    'size_mb': size / (1024 * 1024),
                    'size_gb': size / (1024 * 1024 * 1024),
                    'is_system': is_system,
                    'movable': not is_system and size > 100 * 1024 * 1024  # 大于100MB可移动
                })
        except (PermissionError, OSError) as e:
            print(f"扫描错误: {e}")
        
        # 按大小排序
        folders.sort(key=lambda x: x['size'], reverse=True)
        return folders
    
    def get_user_folders(self, max_depth: int = None) -> List[Dict]:
        """获取用户文件夹（文档、视频、图片等）
        
        Args:
            max_depth: 最大深度限制（None表示无限深度）
        """
        user_folders = []
        user_home = Path.home()
        
        common_folders = ['Documents', 'Videos', 'Pictures', 'Downloads', 'Music']
        
        for folder_name in common_folders:
            folder_path = user_home / folder_name
            if folder_path.exists():
                # 使用无限深度扫描
                size = self.get_folder_size(str(folder_path), max_depth=max_depth)
                user_folders.append({
                    'name': folder_name,
                    'path': str(folder_path),
                    'size': size,
                    'size_mb': size / (1024 * 1024),
                    'size_gb': size / (1024 * 1024 * 1024),
                    'is_system': False,
                    'movable': True
                })
        
        return user_folders
    
    def format_size(self, bytes_size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} PB"
    
    def is_admin(self) -> bool:
        """检查是否具有管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def get_folder_size_fast(self, path: str, progress_callback=None) -> int:
        """快速计算文件夹大小（完整扫描）"""
        total_size = 0
        file_count = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                        file_count += 1
                        # 不再报告单个文件夹的扫描进度
                        pass
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass
        return total_size
    
    def get_drive_analysis(self, drive_letter: str, progress_callback=None, use_parallel=True, max_workers=None) -> Dict:
        """获取指定磁盘的完整容量分析"""
        drive = drive_letter if drive_letter.endswith("\\") else drive_letter + "\\"
        
        # 动态设置线程数
        if max_workers is None:
            cpu_count = os.cpu_count() or 4
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
                
                # 收集文件夹列表
                folder_list = []
                for entry in os.scandir(drive):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            root_files_size += entry.stat().st_size
                        elif entry.is_dir(follow_symlinks=False):
                            folder_list.append((entry.path, entry.name, entry.name in self.system_folders))
                    except (OSError, PermissionError):
                        continue
                
                # 定义扫描函数
                def scan_one_folder(path, name, is_sys):
                    size = self.get_folder_size_fast(path, progress_callback)
                    return {
                        'name': name,
                        'path': path,
                        'size': size,
                        'is_system': is_sys,
                        'percent_of_disk': (size / usage.used) * 100 if usage.used > 0 else 0,
                        'percent_of_total': (size / usage.total) * 100 if usage.total > 0 else 0
                    }
                
                # 并行扫描
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(scan_one_folder, path, name, is_sys): name for path, name, is_sys in folder_list}
                    
                    completed = 0
                    total = len(futures)
                    last_reported_percent = 0
                    
                    for future in as_completed(futures):
                        folder_name = futures[future]
                        completed += 1
                        
                        try:
                            result = future.result()
                            folders.append(result)
                            
                            # 每完成10%报告一次
                            current_percent = int((completed / total) * 100)
                            if current_percent >= last_reported_percent + 10:
                                if progress_callback:
                                    progress_callback(f"深度扫描进度: {current_percent}% ({completed}/{total})")
                                last_reported_percent = current_percent
                        except Exception as e:
                            pass  # 静默处理失败
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
                            
                            size = self.get_folder_size_fast(entry.path, progress_callback)
                            
                            if progress_callback:
                                progress_callback(f"✓ {folder_name}: {self.format_size(size)}")
                            
                            folders.append({
                                'name': folder_name,
                                'path': entry.path,
                                'size': size,
                                'is_system': is_system,
                                'percent_of_disk': (size / usage.used) * 100 if usage.used > 0 else 0,
                                'percent_of_total': (size / usage.total) * 100 if usage.total > 0 else 0
                            })
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
