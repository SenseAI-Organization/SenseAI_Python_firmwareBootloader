import tkinter as tk
import sys, os
sys.path.append('.')
from firmwareBootLoader import ESP32Flasher

root = tk.Tk()
root.withdraw()
app = ESP32Flasher(root)

try:
    app._build_spiffs_image('test_data','test_spiffs.bin',1024*1024)
    print('OK')
except Exception as e:
    print('ERROR', e)
finally:
    root.destroy()
