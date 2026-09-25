"""
Build page-specific manual indexes for Resolve pages from the existing combined
manual_index.json.

Creates the following JSON files under data/:
- index_Color.json
- index_Edit.json
- index_Cut.json
- index_Media.json
- index_Fusion.json
- index_Fairlight.json
- index_Deliver.json

The combined manual_index.json remains the canonical backup/reference source.
This script reads it and derives page-specific indexes for local retrieval/citation.
"""
from __future__ import annotations
import argparse
import json
import os
import re
from typing import Dict, Any, List, Iterable

KEYWORD_MAP = {
    'Color': [
        'color', 'grading', 'grade', 'curves', 'vectorscope', 'hue', 'saturation',
        'luma', 'lut', 'qualifier', 'scopes', 'skin tone', 'tone mapping',
        'color page', 'colorist'
    ],
    'Edit': [
        'edit', 'timeline', 'trim', 'marker', 'transition', 'multicam', 'cut',
        'track', 'insert', 'overwrite', 'source tape', 'sync', 'audio edit'
    ],
    'Cut': [
        'cut page', 'cut', 'rough cut', 'source tape', 'sync bin', 'splice',
        'timeline', 'edit decision', 'cutting'
    ],
    'Media': [
        'media pool', 'import', 'proxy', 'optimized media', 'metadata', 'transcode',
        'media management', 'transcoding', 'camera raw', 'archive', 'media'
    ],
    'Fusion': [
        'fusion', 'node', 'merge', 'composite', 'matte', 'mask', 'connect', 'merge node',
        'effect', 'image processing', 'keyer', 'background'
    ],
    'Fairlight': [
        'fairlight', 'audio', 'mixer', 'track', 'bus', 'eq', 'waveform', 'dialogue',
        'ambience', 'microphone', 'mix', 'fader', 'reverb'
    ],
    'Deliver': [
        'deliver', 'render', 'export', 'render queue', 'output', 'encode', 'format',
        'preset', 'render settings', 'streaming', 'master'
    ],
}


def normalize_text(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '')).strip().lower()


def get_matched_keywords(text: str, keywords: Iterable[str]) -> List[str]:
    norm = normalize_text(text)
    hits: List[str] = []
    for kw in keywords:
        if kw.lower() in norm:
            hits.append(kw)
    return hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manual-index', default='data/manual_index.json')
    parser.add_argument('--out-dir', default='data')
    args = parser.parse_args()

    with open(args.manual_index, 'r', encoding='utf-8') as f:
        manual_index = json.load(f)

    os.makedirs(args.out_dir, exist_ok=True)

    # Rebuild indexes from the combined manual_index with page-level keyword matching.
    for category, keywords in KEYWORD_MAP.items():
        page_entries = []
        for doc in manual_index.get('docs', []):
            for page in doc.get('pages', []):
                text_path = page.get('text_path')
                if not text_path:
                    continue
                try:
                    with open(text_path, 'r', encoding='utf-8') as f:
                        full_text = f.read()
                except Exception:
                    full_text = page.get('snippet', '')
                hits = get_matched_keywords(full_text, keywords)
                if not hits:
                    continue
                page_entries.append({
                    'doc_id': doc['id'],
                    'page_number': page.get('page_number'),
                    'text_path': text_path,
                    'snippet': page.get('snippet'),
                    'embedding': page.get('embedding'),
                    'matched_keywords': hits,
                })

        index_obj = {
            'version': 1,
            'category': category,
            'source_manual_index': args.manual_index,
            'page_count': len(page_entries),
            'pages': page_entries,
            'keyword_set': keywords,
        }
        out_path = os.path.join(args.out_dir, f'index_{category}.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(index_obj, f, ensure_ascii=False, indent=2)
        print(f'Wrote {out_path} with {len(page_entries)} pages')

if __name__ == '__main__':
    main()
