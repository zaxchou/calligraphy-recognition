import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.image_search import ImageSearchEngine


def main():
    parser = argparse.ArgumentParser(description="构建图像相似度搜索索引")
    parser.add_argument("--artist", default="all", help="限定画家 (默认全部)")
    parser.add_argument("--force", action="store_true", help="强制重建索引")
    args = parser.parse_args()

    engine = ImageSearchEngine()

    if engine.total_indexed > 0 and not args.force:
        print(f"已有索引: {engine.total_indexed} 条。加 --force 强制重建。")
        return

    print(f"开始构建索引 (artist={args.artist})...")
    result = engine.build_index(artist=args.artist)
    print(result)


if __name__ == "__main__":
    main()
