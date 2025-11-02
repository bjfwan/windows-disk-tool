import ctypes
from ctypes import wintypes
import os

# Windows API structures and constants
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
FILE_ATTRIBUTE_DIRECTORY = 0x10
FIND_FIRST_EX_LARGE_FETCH = 2
FindExInfoBasic = 1
FindExSearchNameMatch = 0

class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD)]

class WIN32_FIND_DATAW(ctypes.Structure):
    _fields_ = [("dwFileAttributes", wintypes.DWORD),
                ("ftCreationTime", FILETIME),
                ("ftLastAccessTime", FILETIME),
                ("ftLastWriteTime", FILETIME),
                ("nFileSizeHigh", wintypes.DWORD),
                ("nFileSizeLow", wintypes.DWORD),
                ("dwReserved0", wintypes.DWORD),
                ("dwReserved1", wintypes.DWORD),
                ("cFileName", wintypes.WCHAR * 260),
                ("cAlternateFileName", wintypes.WCHAR * 14)]

# Load kernel32.dll
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Define API functions
FindFirstFileExW = kernel32.FindFirstFileExW
FindFirstFileExW.argtypes = [
    wintypes.LPCWSTR,
    ctypes.c_int,
    ctypes.POINTER(WIN32_FIND_DATAW),
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD
]
FindFirstFileExW.restype = wintypes.HANDLE

FindNextFileW = kernel32.FindNextFileW
FindNextFileW.argtypes = [wintypes.HANDLE, ctypes.POINTER(WIN32_FIND_DATAW)]
FindNextFileW.restype = wintypes.BOOL

FindClose = kernel32.FindClose
FindClose.argtypes = [wintypes.HANDLE]
FindClose.restype = wintypes.BOOL

def scan_folder_win(path, max_depth=3, scanned_inodes=None):
    """使用Windows API快速扫描文件夹
    
    Args:
        path: 文件夹路径
        max_depth: 最大深度限制
        scanned_inodes: 循环引用检测集合（可选）
    
    Returns:
        dict: {'size': 总大小, 'files': 文件数, 'folders': 文件夹数}
    """
    if scanned_inodes is None:
        scanned_inodes = set()
    
    return _scan_recursive(path, max_depth, 0, scanned_inodes)

def _scan_recursive(path, max_depth, current_depth, scanned_inodes):
    """递归扫描实现"""
    if max_depth >= 0 and current_depth >= max_depth:
        return {'size': 0, 'files': 0, 'folders': 0}
    
    total_size = 0
    total_files = 0
    total_folders = 0
    
    try:
        search_path = os.path.join(path, '*')
        find_data = WIN32_FIND_DATAW()
        
        hFind = FindFirstFileExW(
            search_path,
            FindExInfoBasic,
            ctypes.byref(find_data),
            FindExSearchNameMatch,
            None,
            FIND_FIRST_EX_LARGE_FETCH
        )
        
        if hFind == INVALID_HANDLE_VALUE:
            return {'size': 0, 'files': 0, 'folders': 0}
        
        try:
            while True:
                filename = find_data.cFileName
                if filename not in ('.', '..'):
                    is_dir = find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY
                    
                    if is_dir:
                        total_folders += 1
                        subdir_path = os.path.join(path, filename)
                        result = _scan_recursive(subdir_path, max_depth, current_depth + 1, scanned_inodes)
                        total_size += result['size']
                        total_files += result['files']
                        total_folders += result['folders']
                    else:
                        file_size = (find_data.nFileSizeHigh << 32) + find_data.nFileSizeLow
                        total_size += file_size
                        total_files += 1
                
                if not FindNextFileW(hFind, ctypes.byref(find_data)):
                    break
        finally:
            FindClose(hFind)
    
    except Exception:
        pass
    
    return {'size': total_size, 'files': total_files, 'folders': total_folders}

# 测试函数
if __name__ == "__main__":
    import time
    
    test_path = r"C:\Users"
    print(f"测试扫描: {test_path}")
    
    start = time.time()
    result = scan_folder_win(test_path, max_depth=3)
    elapsed = time.time() - start
    
    print(f"大小: {result['size'] / (1024**3):.2f} GB")
    print(f"文件数: {result['files']}")
    print(f"文件夹数: {result['folders']}")
    print(f"耗时: {elapsed:.2f} 秒")
