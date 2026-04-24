# -*- coding: utf-8 -*-
"""Two-stage image matching:
Stage 1: Color histogram + pHash quick filter -> top 20 candidates
Stage 2: SIFT + Homography RANSAC -> best match
"""
import cv2, numpy as np, os, sys, configparser, imagehash
from PIL import Image
from collections import Counter

def imread(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)

def gray(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)

ini_path = os.path.join(os.path.dirname(__file__), 'paths.ini')
cfg = configparser.ConfigParser()
cfg.read(ini_path, encoding='utf-8')

user_img = cfg['paths']['user_img']
ref_dir  = cfg['paths']['ref_dir']

# ============================================================
# Stage 1: Quick filter using color histogram + pHash
# ============================================================
img1_col = imread(user_img)
img1_gry = gray(user_img)
print(f'User image: {img1_col.shape}')

# Color histogram (16 bins per channel)
hist1 = cv2.calcHist([img1_col], [0,1,2], None, [16,16,16], [0,256,0,256,0,256])
cv2.normalize(hist1, hist1).ravel()

# pHash
phash1 = imagehash.phash(Image.fromarray(cv2.cvtColor(img1_col, cv2.COLOR_BGR2RGB)))

ref_files = sorted(
    [f for f in os.listdir(ref_dir) if f.lower().endswith(('.jpg', '.jpeg'))],
    key=lambda x: int(''.join(filter(str.isdigit, x.split('-')[0])))
)
print(f'Reference pages: {len(ref_files)}')

hist_scores = []
hash_scores = []
for fname in ref_files:
    fpath = os.path.join(ref_dir, fname)
    img2_col = imread(fpath)
    if img2_col is None:
        continue
    h2 = cv2.calcHist([img2_col], [0,1,2], None, [16,16,16], [0,256,0,256,0,256])
    cv2.normalize(h2, h2).ravel()
    score = cv2.compareHist(hist1, h2, cv2.HISTCMP_CORREL)
    hist_scores.append((fname, score))
    try:
        phash2 = imagehash.phash(Image.fromarray(cv2.cvtColor(img2_col, cv2.COLOR_BGR2RGB)))
        hdist = phash1 - phash2
        hash_scores.append((fname, hdist))
    except Exception:
        pass

# Top 20 by histogram
top_hist = sorted(hist_scores, key=lambda x: x[1], reverse=True)[:20]
print('\nTop 20 by color histogram:')
for fname, s in top_hist:
    print(f'  {fname}: hist={s:.3f}')

# Top 20 by pHash (lowest distance)
top_hash = sorted(hash_scores, key=lambda x: x[1])[:20]
print('\nTop 20 by pHash distance:')
for fname, d in top_hash:
    print(f'  {fname}: hdist={d}')

# Union of top candidates
candidates = list(dict.fromkeys([f for f, _ in top_hist[:10]] + [f for f, _ in top_hash[:10]]))
print(f'\nCandidate pool: {len(candidates)} pages -> {candidates}')

# ============================================================
# Stage 2: SIFT on candidates only
# ============================================================
sift = cv2.SIFT_create(nOctaveLayers=5, contrastThreshold=0.05, edgeThreshold=10, sigma=0.8)
kp1, des1 = sift.detectAndCompute(img1_gry, None)
print(f'\nUser keypoints: {len(kp1)}')

bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

sift_results = []
for fname in candidates:
    fpath = os.path.join(ref_dir, fname)
    img2_gry = gray(fpath)
    if img2_gry is None:
        continue
    kp2, des2 = sift.detectAndCompute(img2_gry, None)
    if des2 is None or len(kp2) < 20:
        continue

    matches = bf.knnMatch(des1, des2, k=2)
    good = [m for m, n in matches if m.distance < 0.7 * n.distance]
    if len(good) < 4:
        continue

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0, maxIters=2000)
    if mask is None:
        continue
    inliers = int(mask.ravel().sum())
    ir = inliers / len(good) if good else 0
    det = float(np.linalg.det(M)) if M is not None else 0
    sift_results.append((fname, len(good), inliers, ir, det))

sift_results.sort(key=lambda x: (x[2], x[1]), reverse=True)
print('\nSIFT results on candidates:')
for fname, n_good, n_inliers, ir, det in sift_results:
    print(f'  {fname}: {n_good} good, {n_inliers} inliers (IR={ir:.2f}, det={det:.1f})')