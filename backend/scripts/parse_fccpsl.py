#!/usr/bin/env python3
"""Parse FCCPSL.owl → extract all C4 words with hierarchy → save as candidate_words.json"""
import re, json, sys, os
from collections import Counter

# Find FCCPSL.owl
search_paths = [
    '/tmp/poetry-sentiment-lexicon/FCCPSL.owl',
    os.path.join(os.path.dirname(__file__), '..', '..', 'tmp', 'poetry-sentiment-lexicon', 'FCCPSL.owl'),
]

owl_path = None
for p in search_paths:
    if os.path.exists(p):
        owl_path = p
        break

if not owl_path:
    print("FCCPSL.owl not found. Clone it first:")
    print("  cd /tmp && git clone --depth 1 https://github.com/Weiiiing/poetry-sentiment-lexicon.git")
    sys.exit(1)

print(f"Reading {owl_path}...")
with open(owl_path, encoding='utf-8') as f:
    content = f.read()

# C3 → C2
c3_to_c2 = {}
for m in re.finditer(r'<owl:Class rdf:ID="(C3_\w+)"><rdfs:subClassOf rdf:resource="#(C2_\w+)"', content):
    c3_to_c2[m.group(1)] = m.group(2)

# C2 → C1
c2_to_c1 = {}
for m in re.finditer(r'<owl:Class rdf:ID="(C2_\w+)"><rdfs:subClassOf rdf:resource="#(C1_\w+)"', content):
    c2_to_c1[m.group(1)] = m.group(2)

# C4 → C3
c4_words = []
for m in re.finditer(r'<owl:Class rdf:ID="C4_([^"]+)"><rdfs:subClassOf rdf:resource="#(C3_\w+)"', content):
    word = m.group(1)
    c3 = m.group(2)
    c2 = c3_to_c2.get(c3, 'unknown')
    c1 = c2_to_c1.get(c2, 'unknown')
    polarity = 'positive' if c1 == 'C1_positive' else 'negative' if c1 == 'C1_negative' else 'unknown'
    c4_words.append({
        'word': word,
        'c3': c3.replace('C3_', ''),
        'c2': c2.replace('C2_', ''),
        'c1_polarity': polarity
    })

print(f"\nTotal words extracted: {len(c4_words)}")

# Stats
c3_counts = Counter(w['c3'] for w in c4_words)
print("\nPer C3 category:")
for c3, count in sorted(c3_counts.items(), key=lambda x: -x[1]):
    print(f"  {c3}: {count}")

# Check for single-character words
single_chars = [w for w in c4_words if len(w['word']) == 1]
multi_chars = [w for w in c4_words if len(w['word']) >= 2]
print(f"\nSingle character: {len(single_chars)}")
print(f"Multi character: {len(multi_chars)}")

# Overlap with existing lexicon
existing_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'emotion_lexicon.json')
if os.path.exists(existing_path):
    with open(existing_path, encoding='utf-8') as f:
        existing = json.load(f)
    existing_words = set(existing.get('entries', {}).keys())
    fccpsl_words = set(w['word'] for w in c4_words)
    overlap = existing_words & fccpsl_words
    new_words = fccpsl_words - existing_words
    print(f"\nExisting lexicon: {len(existing_words)} words")
    print(f"Overlap with FCCPSL: {len(overlap)}")
    print(f"New from FCCPSL: {len(new_words)}")

# Output candidate list
output = {
    'source': 'FCCPSL',
    'version': '1.0',
    'total_words': len(c4_words),
    'words': c4_words
}

out_path = os.path.join(os.path.dirname(__file__), 'fccpsl_candidates.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\nSaved to {out_path}")
print("Done!")
