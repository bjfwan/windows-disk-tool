"""
UI动画效果模块
提供平滑的过渡动画和视觉反馈
"""
import customtkinter as ctk
from typing import Callable, Optional
import threading
import time


class AnimationHelper:
    """动画辅助类 - 提供各种动画效果"""
    
    @staticmethod
    def animate_number(widget, start_value: float, end_value: float, 
                      duration: float = 0.5, format_func: Optional[Callable] = None):
        """
        数字变化动画
        
        Args:
            widget: CTkLabel组件
            start_value: 起始值
            end_value: 结束值
            duration: 动画时长（秒）
            format_func: 格式化函数，如lambda x: f"{x:.2f} GB"
        """
        def animate():
            steps = 30  # 30帧动画
            step_duration = duration / steps
            step_value = (end_value - start_value) / steps
            
            current_value = start_value
            for _ in range(steps):
                current_value += step_value
                display_text = format_func(current_value) if format_func else f"{current_value:.2f}"
                
                try:
                    widget.after(0, lambda t=display_text: widget.configure(text=t))
                except:
                    break  # widget已销毁
                
                time.sleep(step_duration)
            
            # 确保最终值准确
            final_text = format_func(end_value) if format_func else f"{end_value:.2f}"
            try:
                widget.after(0, lambda: widget.configure(text=final_text))
            except:
                pass
        
        threading.Thread(target=animate, daemon=True).start()
    
    @staticmethod
    def fade_in(widget, duration: float = 0.3):
        """
        淡入动画
        
        Args:
            widget: CTk组件
            duration: 动画时长（秒）
        """
        def animate():
            steps = 15
            step_duration = duration / steps
            
            for i in range(steps + 1):
                alpha = i / steps
                try:
                    widget.after(0, lambda a=alpha: widget.configure(fg_color=_get_fade_color(a)))
                except:
                    break
                time.sleep(step_duration)
        
        def _get_fade_color(alpha):
            # 简化版：只改变透明度效果
            return widget.cget("fg_color")
        
        threading.Thread(target=animate, daemon=True).start()
    
    @staticmethod
    def expand_animation(widget, target_height: int, duration: float = 0.2):
        """
        展开动画
        
        Args:
            widget: CTk组件
            target_height: 目标高度
            duration: 动画时长（秒）
        """
        def animate():
            steps = 10
            step_duration = duration / steps
            current_height = 0
            step_height = target_height / steps
            
            for _ in range(steps):
                current_height += step_height
                try:
                    widget.after(0, lambda h=int(current_height): widget.configure(height=h))
                except:
                    break
                time.sleep(step_duration)
            
            # 确保最终高度准确
            try:
                widget.after(0, lambda: widget.configure(height=target_height))
            except:
                pass
        
        threading.Thread(target=animate, daemon=True).start()


class AnimatedProgressBar(ctk.CTkProgressBar):
    """动画进度条 - 平滑过渡的进度条"""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._target_value = 0
        self._animating = False
        self._animation_thread = None
    
    def set_animated(self, value: float, duration: float = 0.3):
        """
        设置进度值（带动画）
        
        Args:
            value: 目标值（0.0 - 1.0）
            duration: 动画时长（秒）
        """
        if self._animating:
            return  # 已有动画在运行
        
        self._target_value = max(0.0, min(1.0, value))
        
        def animate():
            self._animating = True
            start_value = self.get()
            steps = 20
            step_duration = duration / steps
            step_value = (self._target_value - start_value) / steps
            
            current_value = start_value
            for _ in range(steps):
                if not self._animating:
                    break
                
                current_value += step_value
                try:
                    self.after(0, lambda v=current_value: self.set(v))
                except:
                    break
                
                time.sleep(step_duration)
            
            # 确保最终值准确
            try:
                self.after(0, lambda: self.set(self._target_value))
            except:
                pass
            
            self._animating = False
        
        self._animation_thread = threading.Thread(target=animate, daemon=True)
        self._animation_thread.start()
    
    def set_instant(self, value: float):
        """
        立即设置进度值（无动画）
        
        Args:
            value: 目标值（0.0 - 1.0）
        """
        self._animating = False
        self.set(value)
    
    def pulse(self, duration: float = 1.0):
        """
        脉冲动画（用于不确定的进度）
        
        Args:
            duration: 脉冲周期（秒）
        """
        def animate():
            while self._animating:
                # 从0到1再到0的循环
                for i in range(20):
                    if not self._animating:
                        break
                    value = abs((i - 10) / 10.0)
                    try:
                        self.after(0, lambda v=value: self.set(v))
                    except:
                        return
                    time.sleep(duration / 20)
        
        self._animating = True
        threading.Thread(target=animate, daemon=True).start()
    
    def stop_pulse(self):
        """停止脉冲动画"""
        self._animating = False
