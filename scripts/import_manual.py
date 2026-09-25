"""
Import and index PDF manuals found under docs/manuals/raw.

- Extracts per-page text into docs/manuals/text/<pdf-basename>_page_<n>.md
- Builds data/manual_index.json containing per-page metadata and stub embeddings

Usage:
    python scripts/import_manual.py --raw docs/manuals/raw --text docs/manuals/text --out data/manual_index.json

This uses PyPDF2 for extraction and a deterministic sha256-based stub
embedding so it's usable without heavy ML dependencies.
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import hashlib
from typing import List

from PyPDF2 import PdfReader


def sha256_stub_embedding(text: str, dim: int = 64) -> List[float]:
    h = hashlib.sha256(text.encode('utf-8')).digest()
    out_bytes = h
    while len(out_bytes) < dim * 4:
        h = hashlib.sha256(h).digest()
        out_bytes += h
    vals = []
    for i in range(dim):
        chunk = out_bytes[i * 4:(i + 1) * 4]
        iv = int.from_bytes(chunk, 'big', signed=False)
        vals.append((iv / 0xFFFFFFFF) * 2.0 - 1.0)
    return vals


def ensure_dir(p: str) -> None:
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)


def extract_and_index(raw_dir: str, text_dir: str, out_index: str, embed_dim: int = 64) -> dict:
    ensure_dir(text_dir)
    index = {
        'version': 1,
        'docs': [],
        'count': 0,
        'embed_dim': embed_dim,
    }

    pattern = os.path.join(raw_dir, '*.pdf')
    files = sorted(glob.glob(pattern))
    for pdf_path in files:
        basename = os.path.basename(pdf_path)
        doc_id = os.path.splitext(basename)[0]
        try:
            reader = PdfReader(pdf_path)
        except Exception as e:
            print(f'Failed to read {pdf_path}: {e}')
            continue
        num_pages = len(reader.pages)
        doc_entry = {
            'id': doc_id,
            'filename': basename,
            'pages': [],
            'num_pages': num_pages,
        }
        for i, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            # Save page text as a markdown file
            shortname = f"{doc_id}_page_{i}.md"
            out_path = os.path.join(text_dir, shortname)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(f"# {basename} — page {i}\n\n")
                f.write(text)

            snippet = (text.strip()[:300]) if text else ""
            embedding = sha256_stub_embedding(text or '', dim=embed_dim)
            page_entry = {
                'page_number': i,
                'text_path': os.path.relpath(out_path).replace('\\', '/'),
                'snippet': snippet,
                'embedding': embedding,
            }
            doc_entry['pages'].append(page_entry)
            index['count'] += 1
        index['docs'].append(doc_entry)

    # Write index file
    out_dir = os.path.dirname(out_index)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with open(out_index, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return index


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--raw', required=True, help='Path to docs/manuals/raw')
    p.add_argument('--text', required=True, help='Path to docs/manuals/text output')
    p.add_argument('--out', required=True, help='Output JSON index file')
    p.add_argument('--embed-dim', type=int, default=64)
    args = p.parse_args()

    idx = extract_and_index(args.raw, args.text, args.out, embed_dim=args.embed_dim)
    print(f"Indexed {len(idx['docs'])} documents, {idx['count']} pages total -> {args.out}")


if __name__ == '__main__':
    main()
