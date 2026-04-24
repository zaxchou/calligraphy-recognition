import requests

# 检查 Qdrant 集合
collections_url = "http://localhost:6333/collections"
response = requests.get(collections_url)
print("Collections:")
print(response.json())

# 检查 knowledge_texts 集合
print("\nKnowledge texts collection:")
response = requests.get("http://localhost:6333/collections/knowledge_texts")
print(response.json())

# 统计数量
print("\nKnowledge texts count:")
response = requests.post("http://localhost:6333/collections/knowledge_texts/points/count", json={})
print(response.json())
