"""
动画效果模块 - C3增强功能
提供各种UI动画效果
"""

import customtkinter as ctk
from typing import Callable, Optional

class AnimationHelper:
    """动画辅助类"""
    
    @staticmethod
    def fade_in(widget, duration_ms: int = 300, steps: int = 10):
        """淡入动画
        
        Args:
            widget: 要动画的控件
            duration_ms: 动画持续时间（毫秒）
            steps: 动画步数
        """
        step_delay = duration_ms // steps
        alpha_step = 1.0 / steps
        
        def animate(current_step=0):
            if current_step >= steps:
                return
            
            alpha = alpha_step * (current_step + 1)
            try:
                # CustomTkinter不直接支持透明度，使用位置动画替代
                widget.lift()
                widget.after(step_delay, lambda: animate(current_step + 1))
            except:
                pass
        
        animate()
    
    @staticmethod
    def slide_in(widget, duration_ms: int = 300, from_x: int = 50):
        """滑入动画
        
        Args:
            widget: 要动画的控件
            duration_ms: 动画持续时间（毫秒）
            from_x: 起始X偏移量
        """
        steps = 15
        step_delay = duration_ms // steps
        x_step = from_x / steps
        
        # 保存原始位置
        original_x = widget.winfo_x()
        
        def animate(current_step=0):
            if current_step >= steps:
                return
            
            offset = from_x - (x_step * current_step)
            try:
                widget.place(x=original_x + offset)
                widget.after(step_delay, lambda: animate(current_step + 1))
            except:
                pass
        
        animate()
    
    @staticmethod
    def pulse_effect(widget, duration_ms: int = 500, scale_factor: float = 1.05):
        """脉冲效果（缩放动画）
        
        Args:
            widget: 要动画的控件
            duration_ms: 动画持续时间（毫秒）
            scale_factor: 缩放因子
        """
        steps = 10
        step_delay = duration_ms // (steps * 2)
        
        try:
            original_width = widget.winfo_width()
            original_height = widget.winfo_height()
        except:
            return
        
        def animate(current_step=0, expanding=True):
            if current_step >= steps and not expanding:
                return
            
            if current_step >= steps:
                expanding = False
                current_step = 0
            
            try:
                if expanding:
                    scale = 1.0 + ((scale_factor - 1.0) * current_step / steps)
                else:
                    scale = scale_factor - ((scale_factor - 1.0) * current_step / steps)
                
                new_width = int(original_width * scale)
                new_height = int(original_height * scale)
                
                widget.configure(width=new_width, height=new_height)
                widget.after(step_delay, lambda: animate(current_step + 1, expanding))
            except:
                pass
        
        animate()
    
    @staticmethod
    def progress_bar_animation(progress_bar, target_value: float, duration_ms: int = 500):
        """进度条动画
        
        Args:
            progress_bar: CTkProgressBar控件
            target_value: 目标值（0-1）
            duration_ms: 动画持续时间（毫秒）
        """
        steps = 20
        step_delay = duration_ms // steps
        
        try:
            current_value = progress_bar.get()
        except:
            current_value = 0
        
        value_step = (target_value - current_value) / steps
        
        def animate(current_step=0):
            if current_step >= steps:
                progress_bar.set(target_value)
                return
            
            new_value = current_value + (value_step * (current_step + 1))
            try:
                progress_bar.set(new_value)
                progress_bar.after(step_delay, lambda: animate(current_step + 1))
            except:
                pass
        
        animate()
    
    @staticmethod
    def button_ripple(button, duration_ms: int = 300):
        """按钮波纹效果
        
        Args:
            button: CTkButton控件
            duration_ms: 动画持续时间（毫秒）
        """
        try:
            original_color = button.cget("fg_color")
            hover_color = button.cget("hover_color")
            
            # 快速切换到hover颜色再恢复
            button.configure(fg_color=hover_color)
            button.after(duration_ms, lambda: button.configure(fg_color=original_color))
        except:
            pass
    
    @staticmethod
    def shake_widget(widget, duration_ms: int = 500, intensity: int = 5):
        """摇晃动画（错误提示）
        
        Args:
            widget: 要动画的控件
            duration_ms: 动画持续时间（毫秒）
            intensity: 摇晃强度（像素）
        """
        steps = 10
        step_delay = duration_ms // steps
        
        try:
            original_x = widget.winfo_x()
        except:
            return
        
        offsets = [intensity, -intensity, intensity, -intensity, intensity // 2, -intensity // 2, 0]
        
        def animate(current_step=0):
            if current_step >= len(offsets):
                try:
                    widget.place(x=original_x)
                except:
                    pass
                return
            
            try:
                widget.place(x=original_x + offsets[current_step])
                widget.after(step_delay, lambda: animate(current_step + 1))
            except:
                pass
        
        animate()
    
    @staticmethod
    def rotate_text(label, texts: list, interval_ms: int = 2000):
        """文本轮换动画
        
        Args:
            label: CTkLabel控件
            texts: 文本列表
            interval_ms: 切换间隔（毫秒）
        """
        current_index = 0
        
        def animate():
            nonlocal current_index
            try:
                label.configure(text=texts[current_index])
                current_index = (current_index + 1) % len(texts)
                label.after(interval_ms, animate)
            except:
                pass
        
        animate()
    
    @staticmethod
    def loading_spinner(label, duration_ms: int = 100):
        """加载旋转动画
        
        Args:
            label: CTkLabel控件
            duration_ms: 旋转间隔（毫秒）
        """
        spinners = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        current_index = 0
        
        def animate():
            nonlocal current_index
            try:
                current_text = label.cget("text")
                # 保留原文本，只更新前面的spinner
                if any(s in current_text for s in spinners):
                    # 已有spinner，替换它
                    for s in spinners:
                        current_text = current_text.replace(s, spinners[current_index])
                    label.configure(text=current_text)
                else:
                    # 添加spinner
                    label.configure(text=f"{spinners[current_index]} {current_text}")
                
                current_index = (current_index + 1) % len(spinners)
                label.after(duration_ms, animate)
            except:
                pass
        
        animate()

class AnimatedButton(ctk.CTkButton):
    """带动画效果的按钮"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 绑定点击动画
        self.bind("<Button-1>", self._on_click_animation)
    
    def _on_click_animation(self, event):
        """点击动画"""
        AnimationHelper.button_ripple(self, duration_ms=200)

class AnimatedProgressBar(ctk.CTkProgressBar):
    """带动画效果的进度条"""
    
    def set_animated(self, value: float, duration_ms: int = 500):
        """设置值（带动画）
        
        Args:
            value: 目标值（0-1）
            duration_ms: 动画持续时间（毫秒）
        """
        AnimationHelper.progress_bar_animation(self, value, duration_ms)
