"""
弹窗对话框模块
包含开发者信息弹窗和更新日志弹窗
"""
import customtkinter as ctk
import os
import webbrowser
from PIL import Image


def show_dev_dialog(parent, create_flag=False):
    """显示开发者信息弹窗
    
    Args:
        parent: 父窗口
        create_flag: 是否在关闭时创建标记文件
    """
    flag_file = ".first_run_shown"
    
    # 创建自定义弹窗
    dialog = ctk.CTkToplevel(parent)
    dialog.title("欢迎使用 - 磁盘迁移工具 Pro")
    dialog.geometry("720x750")
    dialog.resizable(False, False)
    
    # 居中显示
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (720 // 2)
    y = (dialog.winfo_screenheight() // 2) - (750 // 2)
    dialog.geometry(f"720x750+{x}+{y}")
    
    # 设置为模态对话框
    dialog.transient(parent)
    dialog.grab_set()
    
    # 处理关闭事件
    def on_closing():
        if create_flag:
            try:
                with open(flag_file, 'w') as f:
                    f.write("shown")
            except:
                pass
        dialog.destroy()
    
    dialog.protocol("WM_DELETE_WINDOW", on_closing)
    
    # 欢迎标题
    title = ctk.CTkLabel(
        dialog,
        text="🎉 欢迎使用磁盘迁移工具 Pro v2.0",
        font=ctk.CTkFont(size=24, weight="bold")
    )
    title.pack(pady=(20, 5))
    
    subtitle = ctk.CTkLabel(
        dialog,
        text="智能管理磁盘空间，让C盘不再爆满！",
        font=ctk.CTkFont(size=14),
        text_color="gray"
    )
    subtitle.pack(pady=(0, 10))
    
    # 开发者信息
    dev_frame = ctk.CTkFrame(dialog, corner_radius=12)
    dev_frame.pack(fill="x", padx=40, pady=(0, 10))
    
    dev_title = ctk.CTkLabel(
        dev_frame,
        text="👨‍💻 关于开发者",
        font=ctk.CTkFont(size=16, weight="bold")
    )
    dev_title.pack(pady=(10, 8))
    
    # 开发者图片（保持宽高比，高清显示）
    try:
        image_path = "image.png"
        if os.path.exists(image_path):
            dev_image = Image.open(image_path)
            
            # 计算保持宽高比的缩放
            original_width, original_height = dev_image.size
            max_size = 150
            
            # 只有当图片尺寸大于max_size时才缩放
            if original_width > max_size or original_height > max_size:
                if original_width > original_height:
                    new_width = max_size
                    new_height = int(original_height * (max_size / original_width))
                else:
                    new_height = max_size
                    new_width = int(original_width * (max_size / original_height))
                
                dev_image = dev_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            else:
                new_width, new_height = original_width, original_height
            
            photo = ctk.CTkImage(light_image=dev_image, dark_image=dev_image, size=(new_width, new_height))
            img_label = ctk.CTkLabel(dev_frame, image=photo, text="")
            img_label.image = photo  # 保持引用
            img_label.pack(pady=8)
    except Exception as e:
        print(f"加载开发者图片失败: {e}")
    
    dev_info = ctk.CTkLabel(
        dev_frame,
        text="感谢使用本工具！如果对你有帮助，欢迎Star⭐或赞助支持",
        font=ctk.CTkFont(size=12),
        text_color="gray"
    )
    dev_info.pack(pady=(0, 10))
    
    # 开发者信息容器（横向三列布局）
    info_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    info_frame.pack(pady=5, padx=50, fill="x")
    
    # 第一列：开发者信息
    dev_col = ctk.CTkFrame(info_frame, fg_color="transparent")
    dev_col.pack(side="left", fill="both", expand=True, padx=5)
    
    dev_label = ctk.CTkLabel(
        dev_col,
        text="🧑‍💻 开发者",
        font=ctk.CTkFont(size=14, weight="bold")
    )
    dev_label.pack(pady=(0, 5))
    
    dev_info_text = ctk.CTkLabel(
        dev_col,
        text="wan",
        font=ctk.CTkFont(size=12)
    )
    dev_info_text.pack()
    
    # 第二列：联系方式
    contact_col = ctk.CTkFrame(info_frame, fg_color="transparent")
    contact_col.pack(side="left", fill="both", expand=True, padx=5)
    
    contact_label = ctk.CTkLabel(
        contact_col,
        text="📧 联系方式",
        font=ctk.CTkFont(size=14, weight="bold")
    )
    contact_label.pack(pady=(0, 5))
    
    email_label = ctk.CTkLabel(
        contact_col,
        text="2632507193@qq.com",
        font=ctk.CTkFont(size=11)
    )
    email_label.pack()
    
    # 第三列：开源项目
    github_col = ctk.CTkFrame(info_frame, fg_color="transparent")
    github_col.pack(side="left", fill="both", expand=True, padx=5)
    
    github_label = ctk.CTkLabel(
        github_col,
        text="🌟 开源项目",
        font=ctk.CTkFont(size=14, weight="bold")
    )
    github_label.pack(pady=(0, 5))
    
    # GitHub链接按钮
    def open_github():
        webbrowser.open("https://github.com/bjfwan/windows-disk-tool")
    
    github_btn = ctk.CTkButton(
        github_col,
        text="访问GitHub",
        command=open_github,
        width=140,
        height=28,
        font=ctk.CTkFont(size=11, weight="bold"),
        fg_color=("blue", "darkblue")
    )
    github_btn.pack()
    
    # 赞助信息容器
    sponsor_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    sponsor_frame.pack(pady=12, padx=50, fill="both", expand=True)
    
    sponsor_label = ctk.CTkLabel(
        sponsor_frame,
        text="💖 支持开发",
        font=ctk.CTkFont(size=18, weight="bold")
    )
    sponsor_label.pack(pady=(0, 5))
    
    sponsor_info = ctk.CTkLabel(
        sponsor_frame,
        text="如果这个工具帮到了你，欢迎支持开发者！",
        font=ctk.CTkFont(size=13)
    )
    sponsor_info.pack(pady=(0, 8))
    
    # 收款码图片显示
    qr_frame = ctk.CTkFrame(sponsor_frame, fg_color="transparent")
    qr_frame.pack(pady=5)
    
    try:
        # 微信收款码
        if os.path.exists("wechat.jpg"):
            wechat_img = Image.open("wechat.jpg")
            wechat_img = wechat_img.resize((210, 280), Image.Resampling.LANCZOS)
            wechat_photo = ctk.CTkImage(light_image=wechat_img, dark_image=wechat_img, size=(210, 280))
            
            wechat_container = ctk.CTkFrame(qr_frame, fg_color="transparent")
            wechat_container.pack(side="left", padx=20)
            
            wechat_label = ctk.CTkLabel(wechat_container, image=wechat_photo, text="")
            wechat_label.image = wechat_photo  # 保持引用
            wechat_label.pack()
            
            wechat_text = ctk.CTkLabel(
                wechat_container, 
                text="微信赞赏", 
                font=ctk.CTkFont(size=15, weight="bold")
            )
            wechat_text.pack(pady=(10, 0))
        
        # 支付宝收款码
        if os.path.exists("apliy.jpg"):
            alipay_img = Image.open("apliy.jpg")
            alipay_img = alipay_img.resize((210, 280), Image.Resampling.LANCZOS)
            alipay_photo = ctk.CTkImage(light_image=alipay_img, dark_image=alipay_img, size=(210, 280))
            
            alipay_container = ctk.CTkFrame(qr_frame, fg_color="transparent")
            alipay_container.pack(side="left", padx=20)
            
            alipay_label = ctk.CTkLabel(alipay_container, image=alipay_photo, text="")
            alipay_label.image = alipay_photo  # 保持引用
            alipay_label.pack()
            
            alipay_text = ctk.CTkLabel(
                alipay_container, 
                text="支付宝打赏", 
                font=ctk.CTkFont(size=15, weight="bold")
            )
            alipay_text.pack(pady=(10, 0))
    
    except Exception as e:
        fallback_label = ctk.CTkLabel(
            sponsor_frame,
            text="收款码图片：wechat.jpg | apliy.jpg",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        fallback_label.pack(pady=5)
    
    # 底部提示
    separator = ctk.CTkFrame(dialog, height=1, fg_color="gray30")
    separator.pack(fill="x", padx=50, pady=(10, 8))
    
    tip_label = ctk.CTkLabel(
        dialog,
        text="💡 此弹窗仅在首次启动时显示，关闭窗口即可开始使用",
        font=ctk.CTkFont(size=11),
        text_color="gray"
    )
    tip_label.pack(pady=(5, 15))


def show_update_log(parent):
    """显示更新记录弹窗
    
    Args:
        parent: 父窗口
    """
    dialog = ctk.CTkToplevel(parent)
    dialog.title("更新记录")
    dialog.geometry("800x700")
    dialog.resizable(True, True)
    
    # 居中显示
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (800 // 2)
    y = (dialog.winfo_screenheight() // 2) - (700 // 2)
    dialog.geometry(f"800x700+{x}+{y}")
    
    dialog.transient(parent)
    dialog.grab_set()
    
    updates = [
        {
            "title": "2025-11-02 重大更新 v2.0",
            "items": [
                "🌲 树形文件夹显示：类似Windows资源管理器，点击展开查看子文件夹",
                "🔍 智能搜索功能：实时模糊搜索，支持名称/路径/缩写匹配",
                "🚀 核心算法重构：消除双重扫描，首次深度扫描提速2倍（10分钟→5分钟）",
                "⚡ 缓存系统升级：引擎实例共享，二次扫描提速20倍（10分钟→30秒）",
                "🧠 智能磁盘检测：自动识别SSD/HDD/NVMe，动态优化线程数",
                "🔐 Windows备份权限：可扫描系统保护文件夹，覆盖率达99%",
                "🎨 动画系统完整实现：数字变化、平滑进度条、淡入淡出效果",
                "📊 详细进度日志：实时显示扫描状态，大文件夹特别提示",
                "💾 内存优化：内存占用降低50%（200MB→100MB）",
                "🎯 数据准确性：统一符号链接处理，准确率100%"
            ]
        },
        {
            "title": "2025-11-01 功能更新",
            "items": [
                "扫描速度优化：循环引用检测、实时速度显示、智能进度报告",
                "扫描覆盖增强：完整支持符号链接与权限预检",
                "界面流畅度：列表显示限制、日志批量刷新、性能更稳",
                "缓存系统：24小时缓存与增量更新"
            ]
        }
    ]
    
    header = ctk.CTkLabel(dialog, text="📜 更新记录", font=ctk.CTkFont(size=22, weight="bold"))
    header.pack(pady=(14, 8))
    
    scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
    scroll.pack(fill="both", expand=True, padx=14, pady=(0, 12))
    
    for u in updates:
        card = ctk.CTkFrame(scroll, corner_radius=12)
        card.pack(fill="x", padx=2, pady=8)
        
        title = ctk.CTkLabel(card, text=f"🗓 {u['title']}", font=ctk.CTkFont(size=16, weight="bold"))
        title.pack(anchor="w", padx=14, pady=(12, 6))
        
        sep = ctk.CTkFrame(card, height=1, fg_color="gray30")
        sep.pack(fill="x", padx=14, pady=(0, 6))
        
        for it in u.get("items", []):
            lbl = ctk.CTkLabel(card, text=f"• {it}", font=ctk.CTkFont(size=13))
            lbl.pack(anchor="w", padx=16, pady=2)
        
        footer_sep = ctk.CTkFrame(card, height=1, fg_color="gray30")
        footer_sep.pack(fill="x", padx=14, pady=(10, 10))
    
    close_btn = ctk.CTkButton(dialog, text="关闭", command=dialog.destroy, width=110, height=36)
    close_btn.pack(pady=(0, 12))
