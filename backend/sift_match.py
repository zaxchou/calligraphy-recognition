"""SIFT feature matching: find which reference page contains the user image."""
import cv2, os, sys, numpy as np

def imread(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)

USER_IMG = sys.argv[1]
REF_DIR = r"E:\李鱓全集\（提取图片）扬州画派书画全集  李鳝_12772971"
TOP_K = 5

# Load user image
img1 = imread(USER_IMG)
if img1 is None:
    print(f"ERROR: cannot load {USER_IMG}")
    sys.exit(1)
print(f"User image: {os.path.basename(USER_IMG)}, shape={img1.shape}")

# SIFT detector
sift = cv2.SIFT_create(nOctaveLayers=3, contrastThreshold=0.04, edgeThreshold=10, sigma=0.5)
kp1, des1 = sift.detectAndCompute(img1, None)
print(f"User image keypoints: {len(kp1)}")

if len(kp1) < 10:
    print("WARNING: too few keypoints in user image")

# BFMatcher with ratio test
bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

results = []
ref_files = sorted([f for f in os.listdir(REF_DIR) if f.endswith('.JPG') or f.endswith('.jpg')],
                  key=lambda x: int(x.replace('第', '').replace('页', '').replace('-', '').replace('.JPG','').replace('.jpg','')))

print(f"Scanning {len(ref_files)} reference pages...")
for fname in ref_files:
    fpath = os.path.join(REF_DIR, fname)
    img2 = imread(fpath)
    if img2 is None:
        continue
    kp2, des2 = sift.detectAndCompute(img2, None)
    if des2 is None or len(kp2) < 10:
        continue

    # KNN match with ratio test
    matches = bf.knnMatch(des1, des2, k=2)
    good = [m for m, n in matches if m.distance < 0.75 * n.distance]
    # Also try Lowe's ratio filter more strictly
    good2 = [m for m, n in matches if m.distance < 0.6 * n.distance]

    results.append((fname, len(good), len(good2), len(kp2)))

results.sort(key=lambda x: x[1], reverse=True)

print(f"\nTop {TOP_K} matches (good matches count / total ref kp):")
for fname, n_good, n_good2, n_ref_kp in results[:TOP_K]:
    print(f"  {fname}: {n_good} good (0.75-ratio) / {n_good2} strict (0.6-ratio) matches, ref kp={n_ref_kp}")
