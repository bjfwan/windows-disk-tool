import os
import shutil
import json
from datetime import datetime
from typing import Optional, Dict, Callable
from concurrent.futures import ThreadPoolExecutor
import threading
from pathlib import Path
import subprocess

class FileMover:
    def __init__(self, max_workers=None):
        self.move_history = []
        self.history_file = "move_history.json"
        # 动态设置线程数（用于大文件并行复制）
        cpu_count = os.cpu_count() or 4
        self.max_workers = max_workers or max(cpu_count * 2, 8)
        self.load_history()
    
    def load_history(self):
        """加载移动历史"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.move_history = json.load(f)
            except:
                self.move_history = []
    
    def save_history(self):
        """保存移动历史"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.move_history, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    def create_junction(self, source: str, target: str) -> bool:
        """创建目录联接（Junction）"""
        try:
            # 使用mklink命令创建junction
            cmd = f'mklink /J "{source}" "{target}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            print(f"创建Junction失败: {e}")
            return False
    
    def move_folder(self, source: str, destination_drive: str, 
                   progress_callback: Optional[Callable] = None,
                   create_link: bool = True) -> dict:
        """
        移动文件夹到目标驱动器
        
        Args:
            source: 源文件夹路径
            destination_drive: 目标驱动器（如 "D:\\"）
            progress_callback: 进度回调函数
            create_link: 是否创建符号链接
        
        Returns:
            dict: 操作结果
        """
        try:
            source_path = Path(source)
            folder_name = source_path.name
            
            # 创建目标路径
            destination_path = Path(destination_drive) / folder_name
            
            # 检查目标是否已存在
            if destination_path.exists():
                return {
                    'success': False,
                    'error': f"目标文件夹已存在: {destination_path}"
                }
            
            if progress_callback:
                progress_callback(f"开始移动: {source} -> {destination_path}")
            
            # 使用优化的复制方法（大文件并行）
            if progress_callback:
                progress_callback(f"正在复制文件（大文件并行加速）...")
            
            # 使用优化的并行复制
            copy_success = self.copy_folder_optimized(source, str(destination_path), progress_callback)
            
            if not copy_success:
                return {
                    'success': False,
                    'error': '文件复制失败'
                }
            
            if progress_callback:
                progress_callback(f"复制完成，准备删除原文件夹...")
            
            # 删除原文件夹
            shutil.rmtree(source)
            
            # 创建Junction链接
            link_created = False
            if create_link:
                if progress_callback:
                    progress_callback(f"创建符号链接...")
                link_created = self.create_junction(source, str(destination_path))
            
            # 记录操作历史
            history_entry = {
                'source': source,
                'destination': str(destination_path),
                'link_created': link_created,
                'timestamp': str(Path.cwd())
            }
            self.move_history.append(history_entry)
            self.save_history()
            
            if progress_callback:
                progress_callback(f"✓ 移动完成！")
            
            return {
                'success': True,
                'source': source,
                'destination': str(destination_path),
                'link_created': link_created
            }
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"✗ 错误: {str(e)}")
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def undo_last_move(self) -> dict:
        """撤销最后一次移动操作"""
        if not self.move_history:
            return {'success': False, 'error': '没有可撤销的操作'}
        
        last_move = self.move_history[-1]
        
        try:
            source = last_move['source']
            destination = last_move['destination']
            
            # 如果存在Junction，先删除
            if os.path.exists(source):
                if os.path.islink(source) or self._is_junction(source):
                    os.rmdir(source)
            
            # 移动回原位置
            shutil.move(destination, source)
            
            # 移除历史记录
            self.move_history.pop()
            self.save_history()
            
            return {
                'success': True,
                'message': f'已恢复: {source}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _is_junction(self, path: str) -> bool:
        """检查路径是否为Junction"""
        try:
            return os.path.isdir(path) and os.path.islink(path)
        except:
            return False
    
    def get_history(self) -> list:
        """获取移动历史"""
        return self.move_history
    
    def _copy_file_parallel(self, src_file: str, dst_file: str, chunk_size: int = 8*1024*1024) -> bool:
        """并行复制大文件（分块并行）
        
        Args:
            src_file: 源文件路径
            dst_file: 目标文件路径
            chunk_size: 分块大小（默认8MB）
        
        Returns:
            是否成功
        """
        try:
            file_size = os.path.getsize(src_file)
            
            # 小于50MB的文件直接复制
            if file_size < 50 * 1024 * 1024:
                shutil.copy2(src_file, dst_file)
                return True
            
            # 大文件分块并行复制
            num_chunks = (file_size + chunk_size - 1) // chunk_size
            
            # 先创建目标文件（预分配空间）
            with open(dst_file, 'wb') as f:
                f.seek(file_size - 1)
                f.write(b'\0')
            
            # 定义复制单个块的函数
            def copy_chunk(chunk_info):
                chunk_num, start, end = chunk_info
                try:
                    with open(src_file, 'rb') as fsrc:
                        fsrc.seek(start)
                        data = fsrc.read(end - start)
                    
                    with open(dst_file, 'r+b') as fdst:
                        fdst.seek(start)
                        fdst.write(data)
                    
                    return True
                except Exception as e:
                    print(f"Chunk {chunk_num} error: {e}")
                    return False
            
            # 创建分块信息
            chunks = []
            for i in range(num_chunks):
                start = i * chunk_size
                end = min((i + 1) * chunk_size, file_size)
                chunks.append((i, start, end))
            
            # 并行复制所有块
            with ThreadPoolExecutor(max_workers=min(num_chunks, self.max_workers)) as executor:
                results = list(executor.map(copy_chunk, chunks))
            
            # 验证所有块都成功
            if all(results):
                # 复制文件属性
                shutil.copystat(src_file, dst_file)
                return True
            else:
                # 有块失败，删除目标文件
                if os.path.exists(dst_file):
                    os.remove(dst_file)
                return False
                
        except Exception as e:
            print(f"Parallel copy error: {e}")
            if os.path.exists(dst_file):
                try:
                    os.remove(dst_file)
                except:
                    pass
            return False
    
    def copy_folder_optimized(self, source: str, destination: str, 
                            progress_callback: Optional[Callable] = None) -> bool:
        """优化的文件夹复制（大文件并行）
        
        Args:
            source: 源文件夹
            destination: 目标文件夹
            progress_callback: 进度回调
        
        Returns:
            是否成功
        """
        try:
            os.makedirs(destination, exist_ok=True)
            
            # 收集所有文件
            all_files = []
            for root, dirs, files in os.walk(source):
                # 创建对应的目录结构
                rel_path = os.path.relpath(root, source)
                dst_dir = os.path.join(destination, rel_path)
                os.makedirs(dst_dir, exist_ok=True)
                
                # 收集文件信息
                for file in files:
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(dst_dir, file)
                    file_size = os.path.getsize(src_file)
                    all_files.append((src_file, dst_file, file_size))
            
            # 按文件大小排序（大文件优先，充分利用并行）
            all_files.sort(key=lambda x: x[2], reverse=True)
            
            total_files = len(all_files)
            completed = 0
            
            # 并行处理文件
            def copy_one_file(file_info):
                src, dst, size = file_info
                try:
                    # 大文件使用并行复制
                    if size > 50 * 1024 * 1024:
                        return self._copy_file_parallel(src, dst)
                    else:
                        shutil.copy2(src, dst)
                        return True
                except:
                    return False
            
            # 使用所有可用线程进行并行复制
            from concurrent.futures import as_completed
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(copy_one_file, f) for f in all_files]
                
                for future in as_completed(futures):
                    if future.result():
                        completed += 1
                        # 降低进度更新频率，减少UI卡顿
                        if progress_callback and completed % 50 == 0:
                            progress_callback(f"复制进度: {completed}/{total_files}")
            
            if progress_callback:
                progress_callback(f"✓ 复制完成！共 {completed}/{total_files} 个文件")
            
            return completed == total_files
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"✗ 复制失败: {e}")
            return False
