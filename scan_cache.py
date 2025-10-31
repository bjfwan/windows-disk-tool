import json
import time
import os
from pathlib import Path
from typing import Optional, Dict, Tuple

class ScanCache:
    """扫描结果缓存管理 - 支持增量智能缓存"""
    
    def __init__(self, cache_file="scan_cache.json", expire_hours=24):
        self.cache_file = cache_file
        self.expire_seconds = expire_hours * 3600
        self.cache = self._load_cache()
        # 增量缓存：记录每个文件夹的修改时间和大小
        self.folder_cache = self.cache.get('folders', {})
    
    def _load_cache(self) -> Dict:
        """加载缓存文件"""
        try:
            if Path(self.cache_file).exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _save_cache(self):
        """保存缓存文件"""
        try:
            # 保存文件夹缓存
            self.cache['folders'] = self.folder_cache
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    def get(self, key: str) -> Optional[Dict]:
        """获取缓存数据"""
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        timestamp = entry.get('timestamp', 0)
        
        # 检查是否过期
        if time.time() - timestamp > self.expire_seconds:
            del self.cache[key]
            self._save_cache()
            return None
        
        return entry.get('data')
    
    def set(self, key: str, data: Dict):
        """设置缓存数据"""
        self.cache[key] = {
            'timestamp': time.time(),
            'data': data
        }
        self._save_cache()
    
    def clear(self, key: Optional[str] = None):
        """清除缓存"""
        if key:
            if key in self.cache:
                del self.cache[key]
        else:
            self.cache = {}
        self._save_cache()
    
    def get_cache_age(self, key: str) -> Optional[int]:
        """获取缓存年龄（秒）"""
        if key not in self.cache:
            return None
        
        timestamp = self.cache[key].get('timestamp', 0)
        return int(time.time() - timestamp)
    
    def has_valid_cache(self, key: str) -> bool:
        """检查是否有有效缓存"""
        return self.get(key) is not None
    
    def _get_folder_mtime(self, path: str) -> float:
        """获取文件夹的修改时间
        
        Args:
            path: 文件夹路径
            
        Returns:
            修改时间戳（秒）
        """
        try:
            return os.path.getmtime(path)
        except (OSError, PermissionError):
            return 0
    
    def get_folder_cache(self, path: str) -> Optional[Tuple[int, float]]:
        """获取文件夹缓存（增量缓存）
        
        Args:
            path: 文件夹路径
            
        Returns:
            (size, mtime) 或 None
        """
        if path not in self.folder_cache:
            return None
        
        cached = self.folder_cache[path]
        cached_mtime = cached.get('mtime', 0)
        cached_size = cached.get('size', 0)
        cached_time = cached.get('cache_time', 0)
        
        # 检查缓存是否过期
        if time.time() - cached_time > self.expire_seconds:
            return None
        
        # 检查文件夹是否被修改
        current_mtime = self._get_folder_mtime(path)
        if current_mtime > cached_mtime:
            return None
        
        return (cached_size, cached_mtime)
    
    def set_folder_cache(self, path: str, size: int):
        """设置文件夹缓存（增量缓存）
        
        Args:
            path: 文件夹路径
            size: 文件夹大小（字节）
        """
        mtime = self._get_folder_mtime(path)
        self.folder_cache[path] = {
            'size': size,
            'mtime': mtime,
            'cache_time': time.time()
        }
        self._save_cache()
    
    def is_folder_modified(self, path: str) -> bool:
        """检查文件夹是否被修改（增量检测）
        
        Args:
            path: 文件夹路径
            
        Returns:
            True 表示文件夹已修改或没有缓存
        """
        if path not in self.folder_cache:
            return True
        
        cached_mtime = self.folder_cache[path].get('mtime', 0)
        current_mtime = self._get_folder_mtime(path)
        
        return current_mtime > cached_mtime
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息
        
        Returns:
            缓存统计字典
        """
        total_folders = len(self.folder_cache)
        valid_folders = sum(1 for path in self.folder_cache if not self.is_folder_modified(path))
        
        return {
            'total_folders': total_folders,
            'valid_folders': valid_folders,
            'hit_rate': (valid_folders / total_folders * 100) if total_folders > 0 else 0
        }
