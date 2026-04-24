"""Fix image_path in figure_metadata.json — replace old machine path with current path."""
import json
import os
import sys

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace')

META_PATH = os.path.join(os.path.dirname(__file__), "data", "knowledge", "figure_metadata.json")
OLD_PREFIX = "C:\\Users\\zeroz\\cursor code\\calligraphy-recognition\\backend"
# Also handle forward-slash variant
OLD_PREFIX_FWD = "C:/Users/zeroz/cursor code/calligraphy-recognition/backend"

def main():
    if not os.path.exists(META_PATH):
        print(f"ERROR: {META_PATH} not found")
        sys.exit(1)

    new_base = os.path.abspath(os.path.dirname(__file__))
    # Normalize to forward slashes for consistency
    new_base_norm = new_base.replace("\\", "/")

    with open(META_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    fixed = 0
    missing = 0
    for key, val in data.items():
        ip = val.get("image_path", "")
        if not ip:
            continue
        if OLD_PREFIX in ip:
            new_ip = ip.replace(OLD_PREFIX, new_base).replace("\\", "/")
            val["image_path"] = new_ip
            fixed += 1
        elif OLD_PREFIX_FWD in ip:
            new_ip = ip.replace(OLD_PREFIX_FWD, new_base_norm)
            val["image_path"] = new_ip
            fixed += 1

        # Verify file exists
        check_path = val.get("image_path", "")
        if check_path and not os.path.exists(check_path):
            missing += 1
            if missing <= 3:
                print(f"  WARNING: path not found: {check_path}")

    # Write back
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Fixed {fixed} paths, {missing} still missing")
    if missing == 0 and fixed > 0:
        print("All image_path references are now valid!")

if __name__ == "__main__":
    main()
