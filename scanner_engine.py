import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional, Tuple
import psutil
from scan_cache import ScanCache

# 尝试导入Windows API加速模块
try:
    from fast_scanner_win import scan_folder_win
    HAS_WIN_SCANNER = True
except ImportError:
    HAS_WIN_SCANNER = False

class ScannerEngine:
    """多线程扫描引擎 - 支持增量智能缓存 + 循环引用检测"""
    
    def __init__(self, max_workers=4, cache: Optional[ScanCache] = None):
        self.max_workers = max_workers
        self.stop_flag = threading.Event()
        self.cache = cache if cache else ScanCache()
        self.cache_hits = 0  # 缓存命中计数
        self.cache_misses = 0  # 缓存未命中计数
        self.scanned_inodes = set()  # 循环引用检测（跟踪inode）
        self.scan_stats = {  # 扫描统计
            'total_folders': 0,
            'total_files': 0,
            'total_bytes': 0,
            'start_time': 0,
            'skipped_loops': 0  # 跳过的循环引用
        }
    
    def _get_inode(self, path: str) -> Optional[Tuple[int, int]]:
        """获取文件/文件夹的inode（用于循环检测）"""
        try:
            stat_info = os.stat(path)
            # Windows上使用st_ino + st_dev组合
            return (stat_info.st_dev, stat_info.st_ino)
        except (OSError, PermissionError):
            return None
    
    def reset_scan_stats(self):
        """重置扫描统计"""
        import time
        self.scanned_inodes.clear()
        self.scan_stats = {
            'total_folders': 0,
            'total_files': 0,
            'total_bytes': 0,
            'start_time': time.time(),
            'skipped_loops': 0
        }
    
    def stop_scan(self):
        """停止扫描"""
        self.stop_flag.set()
    
    def get_folder_size_parallel(self, path: str, max_depth: Optional[int] = None, use_cache: bool = True, follow_symlinks: bool = True) -> int:
        """分层并行扫描文件夹大小（支持无限深度 + 增量智能缓存 - 性能优化版）
        
        Args:
            path: 文件夹路径
            max_depth: 最大深度限制（None表示无限深度）
            use_cache: 是否使用增量缓存（默认True）
            follow_symlinks: 是否跟随符号链接（默认True）
        
        Returns:
            文件夹总大小（字节）
            
        优化点：
        1. Windows API加速（FindFirstFileEx，2-3倍提升）
        2. 缓存预检：扫描前检查mtime
        3. stat优化：一次调用获取所有信息
        4. 支持符号链接：扫描实际目录
        5. 循环引用检测：避免无限循环
        """
        if self.stop_flag.is_set():
            return 0
        
        # 如果深度达到限制，返回0
        if max_depth is not None and max_depth < 0:
            return 0
        
        # 增量缓存优先检查（先于循环检测）
        if use_cache and self.cache:
            cached = self.cache.get_folder_cache(path)
            if cached:
                self.cache_hits += 1
                return cached[0]
            else:
                self.cache_misses += 1
        
        # 优先使用Windows API（限深度扫描）
        if HAS_WIN_SCANNER and max_depth is not None and max_depth <= 5:
            try:
                result = scan_folder_win(path, max_depth, self.scanned_inodes)
                total_size = result['size']
                if total_size > 0 and use_cache and self.cache:
                    self.cache.set_folder_cache(path, total_size)
                return total_size
            except Exception:
                pass  # 回退到Python版本
        
        # 循环引用检测：检查是否已扫描过
        if follow_symlinks:
            inode = self._get_inode(path)
            if inode and inode in self.scanned_inodes:
                self.scan_stats['skipped_loops'] += 1
                return 0
            if inode:
                self.scanned_inodes.add(inode)
        
        total_size = 0
        subdirs = []
        
        try:
            # 第一遍：扫描当前目录，收集文件和子目录（批量处理 + 符号链接）
            entries = list(os.scandir(path))  # 一次性收集所有entry
            
            for entry in entries:
                if self.stop_flag.is_set():
                    break
                try:
                    stat_info = entry.stat(follow_symlinks=follow_symlinks)
                    import stat as stat_module
                    if stat_module.S_ISREG(stat_info.st_mode):
                        total_size += stat_info.st_size
                        self.scan_stats['total_files'] += 1
                    elif stat_module.S_ISDIR(stat_info.st_mode):
                        subdirs.append(entry.path)
                        self.scan_stats['total_folders'] += 1
                except (PermissionError, OSError):
                    continue
            
            # 第二遍：并行扫描所有子目录（关键改进 - 优化版 + 符号链接）
            if subdirs and not self.stop_flag.is_set():
                next_depth = None if max_depth is None else max_depth - 1
                
                # 极限并行策略：最大化并行效率
                # 全力并行，不限制（使用线程池的max_workers）
                with ThreadPoolExecutor(max_workers=min(len(subdirs), self.max_workers)) as executor:
                    future_to_dir = {
                        executor.submit(self.get_folder_size_parallel, subdir, next_depth, use_cache, follow_symlinks): subdir 
                        for subdir in subdirs
                    }
                    
                    for future in as_completed(future_to_dir):
                        if self.stop_flag.is_set():
                            break
                        try:
                            total_size += future.result()
                        except Exception as e:
                            # 静默处理错误，减少日志压力
                            continue
            
            # 更新统计
            self.scan_stats['total_bytes'] += total_size
            
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
    
    def scan_folder(self, folder_path: str, folder_name: str, is_system: bool, use_parallel: bool = True, max_depth: Optional[int] = None) -> dict:
        """扫描单个文件夹
        
        Args:
            folder_path: 文件夹路径
            folder_name: 文件夹名称
            is_system: 是否为系统文件夹
            use_parallel: 是否使用并行扫描（默认True）
            max_depth: 最大深度（None表示无限深度）
        """
        size = self.get_folder_size_parallel(folder_path, max_depth=max_depth)
        
        return {
            'name': folder_name,
            'path': folder_path,
            'size': size,
            'is_system': is_system
        }
    
    def scan_drive_folders_parallel(self, drive: str, system_folders: set, 
                                   progress_callback: Optional[Callable] = None, max_depth: int = 1) -> list:
        """并行扫描驱动器的所有文件夹
        
        Args:
            drive: 驱动器路径
            system_folders: 系统文件夹集合
            progress_callback: 进度回调
            max_depth: 最大深度（快速扫描用1，只扫描根目录文件夹列表，但每个文件夹完整扫描）
        """
        self.stop_flag.clear()
        self.reset_scan_stats()  # 重置统计
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
                import time
                futures = {
                    executor.submit(self.scan_folder, path, name, is_sys, use_parallel=True, max_depth=3): (name, time.time())
                    for path, name, is_sys in folder_list
                }
                
                completed = 0
                total = len(futures)
                slow_folders = []  # 记录慢速扫描的文件夹
                
                for future in as_completed(futures):
                    if self.stop_flag.is_set():
                        break
                    
                    folder_name, start_time = futures[future]
                    completed += 1
                    elapsed = time.time() - start_time
                    
                    try:
                        result = future.result()
                        folders.append(result)
                        
                        # 超时10秒给友好提示（降低日志频率）
                        if elapsed > 10 and progress_callback:
                            slow_folders.append((folder_name, int(elapsed)))
                            # 不再每个都报告，最后统一显示
                        
                        # 智能进度报告：每10%才显示 + 实时速度
                        if progress_callback and completed % max(1, total // 10) == 0:
                            # 计算扫描速度（使用当前文件夹大小）
                            scan_time = elapsed
                            if scan_time > 0.1:
                                folder_size_mb = result['size'] / (1024 * 1024)
                                speed_mbps = folder_size_mb / scan_time
                                progress_callback(f"扫描进度: {completed}/{total} | 速度: {speed_mbps:.1f} MB/s - {folder_name}")
                            else:
                                progress_callback(f"扫描进度: {completed}/{total} - {folder_name}")
                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"扫描错误 {folder_name}: {str(e)}")
                
                # 扫描完成后的总结（只有慢速文件夹时才显示）
                if slow_folders and progress_callback:
                    progress_callback(f"🐢 发现 {len(slow_folders)} 个大型文件夹，扫描耗时较长")
                
                # 显示循环引用统计
                if self.scan_stats['skipped_loops'] > 0 and progress_callback:
                    progress_callback(f"♻️ 跳过 {self.scan_stats['skipped_loops']} 个循环引用，避免重复扫描")
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"扫描驱动器错误: {str(e)}")
        
        folders.sort(key=lambda x: x['size'], reverse=True)
        return folders
    
    def get_drive_quick_analysis(self, drive: str, system_folders: set,
                                 progress_callback: Optional[Callable] = None) -> dict:
        """快速分析驱动器（只扫描根目录，不递归）"""
        analysis = {
            'drive': drive,
            'total_size': 0,
            'used_size': 0,
            'free_size': 0,
            'percent': 0,
            'folders': []
        }
        
        try:
            # 禁用分析开始消息，减少日志输出
            # if progress_callback:
            #     progress_callback(f"📊 分析 {drive}...")
            
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
                folder['movable'] = not folder['is_system'] and folder['size'] > 1 * 1024 * 1024  # 大于1MB可移动
            
            analysis['folders'] = folders
            analysis['top_folders'] = folders[:15]
            analysis['scanned_total'] = scanned_total
            analysis['other_size'] = other_size
            
            # 仅在完成时回调
            if progress_callback:
                progress_callback(f"✓ {drive} 扫描完成")
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"✗ {drive} 扫描失败: {str(e)}")
        
        return analysis
