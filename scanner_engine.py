import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional
import psutil
from scan_cache import ScanCache

class ScannerEngine:
    """多线程扫描引擎 - 支持增量智能缓存"""
    
    def __init__(self, max_workers=4, cache: Optional[ScanCache] = None):
        self.max_workers = max_workers
        self.stop_flag = threading.Event()
        self.cache = cache if cache else ScanCache()
        self.cache_hits = 0  # 缓存命中计数
        self.cache_misses = 0  # 缓存未命中计数
    
    def stop_scan(self):
        """停止扫描"""
        self.stop_flag.set()
    
    def get_folder_size_quick(self, path: str, max_depth: int = 2) -> int:
        """快速扫描文件夹大小（限制深度） - 已废弃，使用 get_folder_size_parallel 替代"""
        if self.stop_flag.is_set():
            return 0
        
        total_size = 0
        try:
            for entry in os.scandir(path):
                if self.stop_flag.is_set():
                    break
                try:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False) and max_depth > 0:
                        total_size += self.get_folder_size_quick(entry.path, max_depth - 1)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        return total_size
    
    def _scan_single_path(self, path: str) -> int:
        """扫描单个路径的大小（文件或文件夹）"""
        if self.stop_flag.is_set():
            return 0
        try:
            stat = os.stat(path)
            if os.path.isfile(path):
                return stat.st_size
            return 0
        except (PermissionError, OSError):
            return 0
    
    def get_folder_size_parallel(self, path: str, max_depth: int = None, use_cache: bool = True) -> int:
        """分层并行扫描文件夹大小（支持无限深度 + 增量智能缓存）
        
        Args:
            path: 文件夹路径
            max_depth: 最大深度限制（None表示无限深度）
            use_cache: 是否使用增量缓存（默认True）
        
        Returns:
            文件夹总大小（字节）
        """
        if self.stop_flag.is_set():
            return 0
        
        # 如果深度达到限制，返回0
        if max_depth is not None and max_depth < 0:
            return 0
        
        # 增量缓存检查：如果文件夹未修改，直接返回缓存值
        if use_cache and self.cache:
            cached = self.cache.get_folder_cache(path)
            if cached:
                self.cache_hits += 1
                return cached[0]  # 返回缓存的大小
            else:
                self.cache_misses += 1
        
        total_size = 0
        subdirs = []
        
        try:
            # 第一遍：扫描当前目录，收集文件和子目录
            for entry in os.scandir(path):
                if self.stop_flag.is_set():
                    break
                try:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        subdirs.append(entry.path)
                except (PermissionError, OSError):
                    continue
            
            # 第二遍：并行扫描所有子目录（关键改进 - 优化版）
            if subdirs and not self.stop_flag.is_set():
                next_depth = None if max_depth is None else max_depth - 1
                
                # 极限并行策略：最大化并行效率
                # 全力并行，不限制（使用线程池的max_workers）
                with ThreadPoolExecutor(max_workers=min(len(subdirs), self.max_workers)) as executor:
                    future_to_dir = {
                        executor.submit(self.get_folder_size_parallel, subdir, next_depth, use_cache): subdir 
                        for subdir in subdirs
                    }
                    
                    for future in as_completed(future_to_dir):
                        if self.stop_flag.is_set():
                            break
                        try:
                            total_size += future.result()
                        except Exception as e:
                            print(f"Error scanning {future_to_dir[future]}: {str(e)}")
                            continue
            
            # 保存到增量缓存
            if use_cache and self.cache and total_size > 0:
                self.cache.set_folder_cache(path, total_size)
        
        except (PermissionError, OSError):
            pass
        
        return total_size
    
    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        
        stats = {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate
        }
        
        if self.cache:
            cache_stats = self.cache.get_cache_stats()
            stats.update(cache_stats)
        
        return stats
    
    def scan_folder(self, folder_path: str, folder_name: str, is_system: bool, use_parallel: bool = True, max_depth: int = None) -> dict:
        """扫描单个文件夹
        
        Args:
            folder_path: 文件夹路径
            folder_name: 文件夹名称
            is_system: 是否为系统文件夹
            use_parallel: 是否使用并行扫描（默认True）
            max_depth: 最大深度（None表示无限深度）
        """
        if use_parallel:
            size = self.get_folder_size_parallel(folder_path, max_depth=max_depth)
        else:
            # 兼容旧的快速扫描模式
            depth = 2 if max_depth is None else max_depth
            size = self.get_folder_size_quick(folder_path, max_depth=depth)
        
        return {
            'name': folder_name,
            'path': folder_path,
            'size': size,
            'is_system': is_system
        }
    
    def scan_drive_folders_parallel(self, drive: str, system_folders: set, 
                                   progress_callback: Optional[Callable] = None, max_depth: int = 3) -> list:
        """并行扫描驱动器的所有文件夹
        
        Args:
            drive: 驱动器路径
            system_folders: 系统文件夹集合
            progress_callback: 进度回调
            max_depth: 最大深度（快速扫描用2-3，深度扫描用None）
        """
        self.stop_flag.clear()
        folders = []
        
        try:
            # 获取所有文件夹
            folder_list = []
            for entry in os.scandir(drive):
                if entry.is_dir(follow_symlinks=False):
                    folder_list.append((
                        entry.path,
                        entry.name,
                        entry.name in system_folders
                    ))
            
            # 使用线程池并行扫描
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.scan_folder, path, name, is_sys, use_parallel=True, max_depth=max_depth): name
                    for path, name, is_sys in folder_list
                }
                
                completed = 0
                total = len(futures)
                
                for future in as_completed(futures):
                    if self.stop_flag.is_set():
                        break
                    
                    folder_name = futures[future]
                    completed += 1
                    
                    try:
                        result = future.result()
                        folders.append(result)
                        
                        if progress_callback:
                            progress_callback(f"扫描进度: {completed}/{total} - {folder_name}")
                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"扫描错误 {folder_name}: {str(e)}")
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"扫描驱动器错误: {str(e)}")
        
        folders.sort(key=lambda x: x['size'], reverse=True)
        return folders
    
    def get_drive_quick_analysis(self, drive: str, system_folders: set,
                                 progress_callback: Optional[Callable] = None) -> dict:
        """快速分析驱动器（不深度扫描）"""
        analysis = {
            'drive': drive,
            'total_size': 0,
            'used_size': 0,
            'free_size': 0,
            'percent': 0,
            'folders': []
        }
        
        try:
            if progress_callback:
                progress_callback(f"📊 分析 {drive}...")
            
            usage = psutil.disk_usage(drive)
            analysis['total_size'] = usage.total
            analysis['used_size'] = usage.used
            analysis['free_size'] = usage.free
            analysis['percent'] = usage.percent
            
            # 并行扫描文件夹
            folders = self.scan_drive_folders_parallel(drive, system_folders, progress_callback)
            
            # 计算总和
            scanned_total = sum(f['size'] for f in folders)
            other_size = max(0, usage.used - scanned_total)
            
            # 添加百分比信息
            for folder in folders:
                folder['percent_of_disk'] = (folder['size'] / usage.used * 100) if usage.used > 0 else 0
                folder['movable'] = not folder['is_system'] and folder['size'] > 10 * 1024 * 1024  # 大于10MB可移动
            
            analysis['folders'] = folders
            analysis['top_folders'] = folders[:15]
            analysis['scanned_total'] = scanned_total
            analysis['other_size'] = other_size
            
            if progress_callback:
                progress_callback(f"✓ {drive} 扫描完成")
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"✗ {drive} 扫描失败: {str(e)}")
        
        return analysis
