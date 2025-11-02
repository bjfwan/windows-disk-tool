import sqlite3
import time
import os
from pathlib import Path
from typing import Optional, Dict, Tuple

class ScanCache:
    
    def __init__(self, cache_file="scan_cache.db", expire_hours=24):
        self.cache_file = cache_file
        self.expire_seconds = expire_hours * 3600
        self.conn = None
        import threading
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        self.conn = sqlite3.connect(self.cache_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folder_cache (
                path TEXT PRIMARY KEY,
                size INTEGER NOT NULL,
                mtime REAL NOT NULL,
                cache_time REAL NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_folder_cache_time 
            ON folder_cache(cache_time)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_folder_mtime 
            ON folder_cache(mtime)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS general_cache (
                key TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                data TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_general_timestamp 
            ON general_cache(timestamp)
        """)
        
        self.conn.commit()
        self._cleanup_expired()
    
    def _cleanup_expired(self):
        cursor = self.conn.cursor()
        expire_time = time.time() - self.expire_seconds
        
        cursor.execute("DELETE FROM folder_cache WHERE cache_time < ?", (expire_time,))
        cursor.execute("DELETE FROM general_cache WHERE timestamp < ?", (expire_time,))
        self.conn.commit()
    
    def get(self, key: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT timestamp, data FROM general_cache WHERE key = ?", 
            (key,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        timestamp = row['timestamp']
        if time.time() - timestamp > self.expire_seconds:
            cursor.execute("DELETE FROM general_cache WHERE key = ?", (key,))
            self.conn.commit()
            return None
        
        import json
        return json.loads(row['data'])
    
    def set(self, key: str, data: Dict):
        import json
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO general_cache (key, timestamp, data) VALUES (?, ?, ?)",
                    (key, time.time(), json.dumps(data, ensure_ascii=False))
                )
                self.conn.commit()
            except Exception as e:
                pass
    
    def clear(self, key: Optional[str] = None):
        cursor = self.conn.cursor()
        if key:
            cursor.execute("DELETE FROM general_cache WHERE key = ?", (key,))
        else:
            cursor.execute("DELETE FROM general_cache")
            cursor.execute("DELETE FROM folder_cache")
        self.conn.commit()
    
    def get_cache_age(self, key: str) -> Optional[int]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT timestamp FROM general_cache WHERE key = ?", (key,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return int(time.time() - row['timestamp'])
    
    def has_valid_cache(self, key: str) -> bool:
        return self.get(key) is not None
    
    def _get_folder_mtime(self, path: str) -> float:
        try:
            return os.path.getmtime(path)
        except (OSError, PermissionError):
            return 0
    
    def get_folder_cache(self, path: str) -> Optional[Tuple[int, float]]:
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT size, mtime, cache_time FROM folder_cache WHERE path = ?",
                    (path,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                cached_size = row['size']
                cached_mtime = row['mtime']
                cached_time = row['cache_time']
                
                if time.time() - cached_time > self.expire_seconds:
                    return None
                
                current_mtime = self._get_folder_mtime(path)
                if current_mtime > cached_mtime:
                    return None
                
                return (cached_size, cached_mtime)
            except Exception as e:
                return None
    
    def set_folder_cache(self, path: str, size: int):
        mtime = self._get_folder_mtime(path)
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO folder_cache (path, size, mtime, cache_time) VALUES (?, ?, ?, ?)",
                    (path, size, mtime, time.time())
                )
                self.conn.commit()
            except Exception as e:
                pass
    
    def is_folder_modified(self, path: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT mtime FROM folder_cache WHERE path = ?", (path,))
        row = cursor.fetchone()
        
        if not row:
            return True
        
        cached_mtime = row['mtime']
        current_mtime = self._get_folder_mtime(path)
        
        return current_mtime > cached_mtime
    
    def get_cache_stats(self) -> Dict:
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM folder_cache")
        total_folders = cursor.fetchone()['total']
        
        valid_folders = 0
        cursor.execute("SELECT path FROM folder_cache")
        for row in cursor.fetchall():
            if not self.is_folder_modified(row['path']):
                valid_folders += 1
        
        return {
            'total_folders': total_folders,
            'valid_folders': valid_folders,
            'hit_rate': (valid_folders / total_folders * 100) if total_folders > 0 else 0
        }
    
    def __del__(self):
        if self.conn:
            self.conn.close()
