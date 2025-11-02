"""
磁盘类型检测模块
用于识别SSD、HDD、NVMe等磁盘类型，优化扫描策略
"""
import os
import subprocess
import re
from typing import Optional, Literal

DiskType = Literal['SSD', 'HDD', 'NVME', 'NETWORK', 'UNKNOWN']


class DiskDetector:
    """磁盘类型检测器"""
    
    def __init__(self):
        self._cache = {}  # 缓存检测结果
    
    def get_disk_type(self, drive_letter: str) -> DiskType:
        """
        检测磁盘类型
        
        Args:
            drive_letter: 驱动器盘符，如 "C:\\" 或 "C:"
        
        Returns:
            'SSD', 'HDD', 'NVME', 'NETWORK', 或 'UNKNOWN'
        """
        # 标准化驱动器盘符
        drive = drive_letter.replace('\\', '').replace(':', '')
        
        # 检查缓存
        if drive in self._cache:
            return self._cache[drive]
        
        # 检测磁盘类型
        disk_type = self._detect_disk_type(drive)
        self._cache[drive] = disk_type
        
        return disk_type
    
    def _detect_disk_type(self, drive: str) -> DiskType:
        """
        内部检测逻辑
        
        优先级：
        1. 网络驱动器检测（最快）
        2. PowerShell MSFT_PhysicalDisk 检测（最准确）
        3. WMIC 检测（备用）
        4. 性能测试（兜底）
        """
        # 方法1：检测网络驱动器
        if self._is_network_drive(drive):
            return 'NETWORK'
        
        # 方法2：PowerShell检测（最准确）
        disk_type = self._detect_via_powershell(drive)
        if disk_type != 'UNKNOWN':
            return disk_type
        
        # 方法3：WMIC检测（备用）
        disk_type = self._detect_via_wmic(drive)
        if disk_type != 'UNKNOWN':
            return disk_type
        
        # 方法4：性能测试（兜底）
        return self._detect_via_performance(drive)
    
    def _is_network_drive(self, drive: str) -> bool:
        """检测是否为网络驱动器"""
        try:
            cmd = f'net use {drive}: 2>nul'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
            return result.returncode == 0 and 'Microsoft Windows Network' in result.stdout
        except:
            return False
    
    def _detect_via_powershell(self, drive: str) -> DiskType:
        """
        使用PowerShell检测（最准确的方法）
        
        查询MSFT_PhysicalDisk的MediaType属性：
        - 3 = HDD
        - 4 = SSD
        - 5 = SCM (Storage Class Memory)
        """
        try:
            ps_script = f"""
$partition = Get-Partition -DriveLetter {drive} -ErrorAction SilentlyContinue
if ($partition) {{
    $disk = Get-PhysicalDisk -ErrorAction SilentlyContinue | Where-Object {{ $_.DeviceID -eq $partition.DiskNumber }}
    if ($disk) {{
        Write-Output "$($disk.MediaType)|$($disk.BusType)"
    }}
}}
"""
            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.strip()
                media_type, bus_type = output.split('|') if '|' in output else (output, '')
                
                # 判断MediaType
                if 'SSD' in media_type or media_type == '4':
                    # 进一步判断是否为NVMe
                    if 'NVMe' in bus_type or bus_type == '17':
                        return 'NVME'
                    return 'SSD'
                elif 'HDD' in media_type or media_type == '3':
                    return 'HDD'
        except Exception as e:
            pass
        
        return 'UNKNOWN'
    
    def _detect_via_wmic(self, drive: str) -> DiskType:
        """
        使用WMIC检测（备用方法）
        """
        try:
            # 获取磁盘型号
            cmd = f'wmic diskdrive get Model,MediaType /format:list'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                output = result.stdout.upper()
                
                # 通过型号名称判断
                if 'SSD' in output or 'SOLID STATE' in output:
                    if 'NVME' in output:
                        return 'NVME'
                    return 'SSD'
                elif 'HDD' in output or 'HARD DISK' in output:
                    return 'HDD'
        except:
            pass
        
        return 'UNKNOWN'
    
    def _detect_via_performance(self, drive: str) -> DiskType:
        """
        通过性能测试检测（最后兜底方法）
        
        原理：
        - SSD：随机读取IOPS高（>5000）
        - HDD：随机读取IOPS低（<200）
        """
        try:
            import time
            import random
            
            test_dir = f"{drive}:\\"
            if not os.path.exists(test_dir):
                return 'UNKNOWN'
            
            # 简单的随机读取测试
            test_file = os.path.join(test_dir, 'Windows', 'System32', 'kernel32.dll')
            if not os.path.exists(test_file):
                return 'UNKNOWN'
            
            # 测试10次随机seek+read
            start_time = time.time()
            test_count = 10
            
            with open(test_file, 'rb') as f:
                file_size = os.path.getsize(test_file)
                for _ in range(test_count):
                    offset = random.randint(0, max(0, file_size - 4096))
                    f.seek(offset)
                    f.read(4096)
            
            elapsed = time.time() - start_time
            iops = test_count / elapsed
            
            # 简单判断
            if iops > 1000:  # 很高的IOPS
                return 'SSD'
            elif iops < 100:  # 很低的IOPS
                return 'HDD'
            else:
                return 'SSD'  # 中等IOPS，偏向SSD
            
        except:
            return 'UNKNOWN'
    
    def get_optimal_workers(self, drive_letter: str, cpu_count: int) -> int:
        """
        根据磁盘类型获取最优线程数
        
        Args:
            drive_letter: 驱动器盘符
            cpu_count: CPU核心数
        
        Returns:
            最优线程数
        """
        disk_type = self.get_disk_type(drive_letter)
        
        if disk_type == 'NVME':
            # NVMe SSD：最高并发
            return min(cpu_count * 4, 32)
        
        elif disk_type == 'SSD':
            # SATA SSD：高并发
            return min(cpu_count * 2, 16)
        
        elif disk_type == 'HDD':
            # HDD：单线程或低并发
            return 2  # 保守策略，避免磁头竞争
        
        elif disk_type == 'NETWORK':
            # 网络驱动器：低并发
            return 1
        
        else:  # UNKNOWN
            # 未知类型：使用中等策略
            return min(cpu_count * 2, 8)


# 全局单例
_detector = None

def get_detector() -> DiskDetector:
    """获取全局检测器单例"""
    global _detector
    if _detector is None:
        _detector = DiskDetector()
    return _detector


def get_disk_type(drive_letter: str) -> DiskType:
    """快捷函数：获取磁盘类型"""
    return get_detector().get_disk_type(drive_letter)


def get_optimal_workers(drive_letter: str, cpu_count: int = None) -> int:
    """快捷函数：获取最优线程数"""
    if cpu_count is None:
        cpu_count = os.cpu_count() or 4
    return get_detector().get_optimal_workers(drive_letter, cpu_count)


if __name__ == "__main__":
    # 测试代码
    detector = DiskDetector()
    
    for drive in ['C', 'D', 'E', 'F']:
        drive_path = f"{drive}:\\"
        if os.path.exists(drive_path):
            disk_type = detector.get_disk_type(drive_path)
            workers = detector.get_optimal_workers(drive_path, os.cpu_count() or 4)
            print(f"{drive}盘: {disk_type} → 推荐线程数: {workers}")
