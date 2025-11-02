"""
Windows权限管理模块
启用SeBackupPrivilege和SeRestorePrivilege，允许读取所有文件
"""
import ctypes
from ctypes import wintypes
import os

# Windows常量
SE_PRIVILEGE_ENABLED = 0x00000002
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008

class LUID(ctypes.Structure):
    _fields_ = [
        ('LowPart', wintypes.DWORD),
        ('HighPart', wintypes.LONG),
    ]

class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ('Luid', LUID),
        ('Attributes', wintypes.DWORD),
    ]

class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ('PrivilegeCount', wintypes.DWORD),
        ('Privileges', LUID_AND_ATTRIBUTES * 1),
    ]


class PrivilegeManager:
    """Windows权限管理器"""
    
    def __init__(self):
        self.kernel32 = ctypes.windll.kernel32
        self.advapi32 = ctypes.windll.advapi32
        self._privileges_enabled = False
        self._token_handle = None
    
    def is_admin(self) -> bool:
        """检查是否具有管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def enable_backup_privilege(self) -> bool:
        """
        启用SeBackupPrivilege权限
        
        Returns:
            是否成功启用
        """
        if self._privileges_enabled:
            return True
        
        if not self.is_admin():
            return False
        
        try:
            # 获取当前进程Token
            token_handle = wintypes.HANDLE()
            process_handle = self.kernel32.GetCurrentProcess()
            
            if not self.advapi32.OpenProcessToken(
                process_handle,
                TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                ctypes.byref(token_handle)
            ):
                return False
            
            self._token_handle = token_handle
            
            # 查找SeBackupPrivilege的LUID
            luid = LUID()
            if not self.advapi32.LookupPrivilegeValueW(
                None,
                "SeBackupPrivilege",
                ctypes.byref(luid)
            ):
                return False
            
            # 启用SeBackupPrivilege
            tp = TOKEN_PRIVILEGES()
            tp.PrivilegeCount = 1
            tp.Privileges[0].Luid = luid
            tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
            
            if not self.advapi32.AdjustTokenPrivileges(
                token_handle,
                False,
                ctypes.byref(tp),
                ctypes.sizeof(tp),
                None,
                None
            ):
                return False
            
            # 检查是否有错误
            if self.kernel32.GetLastError() != 0:
                return False
            
            # 同时启用SeRestorePrivilege（用于创建符号链接）
            if not self.advapi32.LookupPrivilegeValueW(
                None,
                "SeRestorePrivilege",
                ctypes.byref(luid)
            ):
                return False
            
            tp.Privileges[0].Luid = luid
            self.advapi32.AdjustTokenPrivileges(
                token_handle,
                False,
                ctypes.byref(tp),
                ctypes.sizeof(tp),
                None,
                None
            )
            
            self._privileges_enabled = True
            return True
            
        except Exception as e:
            return False
    
    def enable_security_privilege(self) -> bool:
        """
        启用SeSecurityPrivilege权限（读取SACL）
        
        Returns:
            是否成功启用
        """
        if not self.is_admin():
            return False
        
        try:
            if not self._token_handle:
                # 先打开token
                token_handle = wintypes.HANDLE()
                process_handle = self.kernel32.GetCurrentProcess()
                
                if not self.advapi32.OpenProcessToken(
                    process_handle,
                    TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                    ctypes.byref(token_handle)
                ):
                    return False
                
                self._token_handle = token_handle
            
            # 查找SeSecurityPrivilege的LUID
            luid = LUID()
            if not self.advapi32.LookupPrivilegeValueW(
                None,
                "SeSecurityPrivilege",
                ctypes.byref(luid)
            ):
                return False
            
            # 启用SeSecurityPrivilege
            tp = TOKEN_PRIVILEGES()
            tp.PrivilegeCount = 1
            tp.Privileges[0].Luid = luid
            tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
            
            if not self.advapi32.AdjustTokenPrivileges(
                self._token_handle,
                False,
                ctypes.byref(tp),
                ctypes.sizeof(tp),
                None,
                None
            ):
                return False
            
            return self.kernel32.GetLastError() == 0
            
        except Exception as e:
            return False
    
    def __del__(self):
        """清理Token句柄"""
        if self._token_handle:
            try:
                self.kernel32.CloseHandle(self._token_handle)
            except:
                pass


# 全局单例
_manager = None

def get_privilege_manager() -> PrivilegeManager:
    """获取全局权限管理器单例"""
    global _manager
    if _manager is None:
        _manager = PrivilegeManager()
    return _manager


def enable_all_privileges() -> bool:
    """
    启用所有必要的权限
    
    Returns:
        是否成功启用
    """
    manager = get_privilege_manager()
    
    if not manager.is_admin():
        return False
    
    backup_ok = manager.enable_backup_privilege()
    security_ok = manager.enable_security_privilege()
    
    return backup_ok or security_ok


if __name__ == "__main__":
    # 测试代码
    manager = PrivilegeManager()
    
    print(f"管理员权限: {manager.is_admin()}")
    
    if manager.is_admin():
        print("尝试启用备份权限...")
        if manager.enable_backup_privilege():
            print("✅ 备份权限已启用！")
            print("现在可以读取所有文件，包括系统文件")
        else:
            print("❌ 无法启用备份权限")
        
        print("\n尝试启用安全权限...")
        if manager.enable_security_privilege():
            print("✅ 安全权限已启用！")
        else:
            print("❌ 无法启用安全权限")
    else:
        print("❌ 需要管理员权限才能启用特权")
