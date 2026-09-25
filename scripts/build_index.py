"""
Minimal index builder for Resolve AI Coach content entries.

- Reads YAML entry files from a content directory (each file is a list of entries).
- Produces a simple on-disk JSON index containing entry metadata and an "embedding".
- Embedding backend is pluggable: if `sentence_transformers` is installed and
  the user passes --use-st-transformers, it will attempt to use it. Otherwise
  a deterministic sha256-based stub embedding is used for local testing.

This is intentionally lightweight so it can be used on developer machines
without heavy ML dependencies.

Usage:
    python scripts/build_index.py --content content/entries --out data/index_color.json

"""
from __future__ import annotations
import argparse
import glob
import json
import os
import hashlib
from typing import List

import yaml


def sha256_stub_embedding(text: str, dim: int = 64) -> List[float]:
    """Create a deterministic numeric embedding from text using SHA256.

    Returns a list of `dim` floats in range [-1, 1]. This is NOT semantically
    meaningful but is reproducible and useful for early integration tests.
    """
    h = hashlib.sha256(text.encode('utf-8')).digest()
    # Expand to enough bytes by repeated hashing if needed
    out_bytes = h
    while len(out_bytes) < dim * 4:
        h = hashlib.sha256(h).digest()
        out_bytes += h
    # Interpret chunks of 4 bytes as signed ints and normalize
    vals = []
    for i in range(dim):
        chunk = out_bytes[i * 4:(i + 1) * 4]
        # big-endian signed int
        iv = int.from_bytes(chunk, 'big', signed=False)
        # Normalize to [-1,1]
        vals.append((iv / 0xFFFFFFFF) * 2.0 - 1.0)
    return vals


def load_entries_from_folder(path: str) -> List[dict]:
    entries = []
    pattern = os.path.join(path, '*.yaml')
    for fn in sorted(glob.glob(pattern)):
        with open(fn, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if not data:
                continue
            if not isinstance(data, list):
                raise ValueError(f"Entry file {fn} must contain a YAML list of entries")
            for item in data:
                item['_source_file'] = os.path.basename(fn)
                entries.append(item)
    return entries


def build_index(entries: List[dict], embed_dim: int = 64, use_st: bool = False) -> dict:
    index = {
        'version': 1,
        'count': len(entries),
        'entries': [],
        'embed_dim': embed_dim,
    }

    # Optionally initialize sentence-transformers model
    st_model = None
    if use_st:
        try:
            from sentence_transformers import SentenceTransformer
            st_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            print('Warning: sentence_transformers requested but failed to load:', e)
            st_model = None

    for ent in entries:
        text = ' '.join([
            ' '.join(ent.get('symptom_phrases', []) or []),
            ent.get('diagnosis', '') or '',
            ent.get('explanation', '') or '',
        ])
        if st_model is not None:
            vec = st_model.encode(text, show_progress_bar=False).tolist()
            # Ensure dim matches requested (may differ for model)
            if len(vec) != embed_dim:
                # Truncate or pad
                if len(vec) > embed_dim:
                    vec = vec[:embed_dim]
                else:
                    vec = vec + [0.0] * (embed_dim - len(vec))
        else:
            vec = sha256_stub_embedding(text, dim=embed_dim)

        entry = {
            'id': ent.get('id'),
            'category': ent.get('category'),
            'symptom_phrases': ent.get('symptom_phrases'),
            'diagnosis': ent.get('diagnosis'),
            'tool_or_technique': ent.get('tool_or_technique'),
            'manual_reference': ent.get('manual_reference'),
            'related_entries': ent.get('related_entries', []),
            'source_file': ent.get('_source_file'),
            'embedding': vec,
        }
        index['entries'].append(entry)

    return index


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--content', required=True, help='Path to content/entries folder')
    p.add_argument('--out', required=True, help='Output index file (JSON)')
    p.add_argument('--embed-dim', type=int, default=64, help='Embedding dimension for stub embeddings')
    p.add_argument('--use-st-transformers', action='store_true', help='Attempt to use sentence-transformers model if available')
    args = p.parse_args()

    entries = load_entries_from_folder(args.content)
    print(f'Loaded {len(entries)} entries from {args.content}')

    index = build_index(entries, embed_dim=args.embed_dim, use_st=args.use_st_transformers)

    out_dir = os.path.dirname(args.out)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f'Wrote index with {index["count"]} entries to {args.out}')


if __name__ == '__main__':
    main()
