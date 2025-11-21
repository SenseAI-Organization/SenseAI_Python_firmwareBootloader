import tkinter as tk
import os
import sys
from firmwareBootLoader import ESP32Flasher

root = tk.Tk()
root.withdraw()
fl = ESP32Flasher(root)

data_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
if not os.path.exists(data_folder):
    print('ERROR: data folder not found:', data_folder)
    sys.exit(2)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spiffs.bin')
size = 983040
print('Building spiffs image to', out)
try:
    fl._build_spiffs_image(data_folder, out, size)
    print('Built:', out, 'size', os.path.getsize(out))
except Exception as e:
    print('Error building:', e)
    sys.exit(1)
