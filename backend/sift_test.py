import cv2, numpy as np, os, sys

def imread(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)

# Test with original file
USER_IMG = r"E:\李鱓全集\修改版\提取图\清_李鱓_麦黄稻熟_0000.jpg"
REF_DIR = r"E:\李鱓全集\（提取图片）扬州画派书画全集  李鳝_12772971"

img1 = imread(USER_IMG)
print(f"User img: {img1.shape}")

sift = cv2.SIFT_create(nOctaveLayers=5, contrastThreshold=0.05, edgeThreshold=10, sigma=0.8)
kp1, des1 = sift.detectAndCompute(img1, None)
print(f"User keypoints: {len(kp1)}")
if des1 is None:
    print("No descriptors!")
    sys.exit(1)

bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

results = []
ref_files = sorted(
    [f for f in os.listdir(REF_DIR) if f.lower().endswith(('.jpg', '.jpeg'))],
    key=lambda x: int(''.join(filter(str.isdigit, x.split('-')[0])))
)
print(f"Reference pages: {len(ref_files)}")

for fname in ref_files:
    fpath = os.path.join(REF_DIR, fname)
    img2 = imread(fpath)
    if img2 is None:
        continue
    kp2, des2 = sift.detectAndCompute(img2, None)
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
    inliers = mask.ravel().sum()
    ir = inliers / len(good) if len(good) > 0 else 0

    results.append((fname, len(good), inliers, ir))

results.sort(key=lambda x: (x[2], x[1]), reverse=True)
print("\nTop 15 matches (sorted by inliers desc, then goods desc):")
for fname, n_good, n_inliers, ir in results[:15]:
    print(f"  {fname}: {n_good} good, {n_inliers} inliers (IR={ir:.2f})")