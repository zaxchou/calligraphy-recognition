#!/bin/bash
export SHELLOPTS
echo '=== DOCKER ==='
sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml ps
echo ''
echo '=== FILE COUNTS ==='
echo "PDFs_in_uploads: $(ls /opt/calligraphy-recognition/backend/data/uploads/*.pdf 2>/dev/null | wc -l)"
echo "Upload_images: $(find /opt/calligraphy-recognition/backend/data/uploads -maxdepth 1 \( -name '*.jpg' -o -name '*.png' \) 2>/dev/null | wc -l)"
echo "Annotated: $(ls /opt/calligraphy-recognition/backend/data/annotated/ 2>/dev/null | wc -l)"
echo "Thumbnails: $(ls /opt/calligraphy-recognition/backend/data/thumbnails/ 2>/dev/null | wc -l)"
echo "Comp_thumbs: $(ls /opt/calligraphy-recognition/backend/data/composition/thumbs/ 2>/dev/null | wc -l)"
echo "Comp_reports: $(ls /opt/calligraphy-recognition/backend/data/composition/reports/*.json 2>/dev/null | wc -l)"
echo "Comp_overlays: $(ls /opt/calligraphy-recognition/backend/data/composition/overlays/*.png 2>/dev/null | wc -l)"
echo "Comp_pdfs: $(ls /opt/calligraphy-recognition/backend/data/composition/pdfs/ 2>/dev/null | wc -l)"
echo "Seals: $(ls /opt/calligraphy-recognition/backend/data/seals/*.png 2>/dev/null | wc -l)"
echo "FAISS_index: $(ls /opt/calligraphy-recognition/backend/data/.image_index/ 2>/dev/null | wc -l)"
echo "Imported_artists: $(ls /opt/calligraphy-recognition/backend/data/imported/ 2>/dev/null)"
echo ''
echo '=== KNOWLEDGE DB ==='
docker exec deploy-backend-1 python3 /tmp/check_db.py 2>&1
echo ''
echo '=== UPLOAD TEST: Composition ==='
docker exec deploy-backend-1 python3 -c 'import requests; r=requests.post("http://localhost:8001/api/v1/composition/upload",files={"file":("x.jpg",open("/app/data/seals/seal_1_20260425015252.png","rb"),"image/jpeg")},timeout=15); print(r.status_code,r.json().get("task_id","?")[:20] if r.ok else r.text[:80])' 2>&1
echo ''
echo '=== UPLOAD TEST: Tubi ==='
docker exec deploy-backend-1 python3 -c 'import requests; r=requests.post("http://localhost:8001/api/v1/tubi/upload",files={"file":("x.jpg",open("/app/data/seals/seal_1_20260425015252.png","rb"),"image/jpeg")},timeout=15); print(r.status_code,r.json().get("image_id","?")[:20] if r.ok else r.text[:80])' 2>&1
echo ''
echo '=== Qczh analyze ==='
docker exec deploy-backend-1 python3 -c 'import requests; r=requests.post("http://localhost:8001/api/v1/composition/qichengzhuanhe-analyze",files={"file":("x.jpg",open("/app/data/seals/seal_1_20260425015252.png","rb"),"image/jpeg")},timeout=30); print(r.status_code,r.json().get("task_id","?")[:20] if r.ok else r.text[:80])' 2>&1
echo ''
echo '=== Content Analysis ==='
curl -sk 'https://localhost/api/v1/content-analysis/artists' 2>&1 | head -c 200
echo ''
echo '=== History ==='
curl -sk 'https://localhost/api/v1/composition/history?limit=2' 2>&1 | python3 -c 'import sys,json; d=json.load(sys.stdin); print("history:",len(d.get("items",[])),"items")'
echo ''
echo '=== Qdrant ==='
python3 /tmp/qdrant_info.py 2>&1
