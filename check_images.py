import cv2
import os

files = os.listdir('data')
print('Files:', files)
for f in files:
    if f.endswith('.png'):
        path = os.path.join('data', f)
        img = cv2.imread(path)
        print(f'{f}: {"OK" if img is not None else "FAIL"}')
