import os
import sys
import winreg
import ctypes
from ctypes import wintypes

class WindowsIntegration:
    """Windows-specific system integration"""
    
    @staticmethod
    def add_to_startup(app_path, app_name="DirectSearch"):
        """Add application to Windows startup"""
        try:
            key = winreg.HKEY_CURRENT_USER
            subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as reg_key:
                winreg.SetValueEx(reg_key, app_name, 0, winreg.REG_SZ, f'"{app_path}" --minimized')
            return True
        except Exception as e:
            print(f"[ERROR] Failed to add to startup: {e}")
            return False
    
    @staticmethod
    def remove_from_startup(app_name="DirectSearch"):
        """Remove application from Windows startup"""
        try:
            key = winreg.HKEY_CURRENT_USER
            subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as reg_key:
                winreg.DeleteValue(reg_key, app_name)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to remove from startup: {e}")
            return False
    
    @staticmethod
    def is_admin():
        """Check if running as administrator"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False