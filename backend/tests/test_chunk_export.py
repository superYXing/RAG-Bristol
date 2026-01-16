"""
test_chunk_export.py - Document Chunking Export Utility

This script processes Markdown files and exports the resulting chunks
to JSON format for inspection and debugging:
- Recursively scans directories for .md files
- Applies the document processor chunking logic
- Exports chunks with metadata to timestamped JSON files

Usage:
    python test_chunk_export.py --dir ../bristol_markdown --out ./chunks
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.ingest import processor


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _iter_markdown_files(root: Path):
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".md"):
                yield Path(dirpath) / name


def _chunk_to_record(chunk: Any, source_rel_path: str, chunk_index: int) -> Dict[str, Any]:
    content = getattr(chunk, "page_content", "")
    metadata = getattr(chunk, "metadata", {}) or {}
    return {
        "source_file": source_rel_path,
        "chunk_index": chunk_index,
        "content": content,
        "metadata": metadata,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Markdown 文件夹路径（递归扫描 .md）")
    parser.add_argument("--out", default="chunks", help="输出 chunks 文件夹路径（默认：./chunks）")
    args = parser.parse_args()

    input_dir = Path(args.dir).expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Invalid --dir: {input_dir}")

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = _ts()
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    out_jsonl = run_dir / "chunks.jsonl"
    manifest_path = run_dir / "manifest.json"

    files = list(_iter_markdown_files(input_dir))
    total_chunks = 0

    with out_jsonl.open("w", encoding="utf-8") as f:
        for file_path in files:
            rel_path = str(file_path.relative_to(input_dir)).replace("\\", "/")
            chunks = processor.process_file(str(file_path))
            for i, chunk in enumerate(chunks, start=1):
                record = _chunk_to_record(chunk, rel_path, i)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1

    manifest = {
        "run_id": run_id,
        "input_dir": str(input_dir),
        "output_dir": str(run_dir),
        "files": len(files),
        "chunks": total_chunks,
        "chunks_file": str(out_jsonl),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Input: {input_dir}")
    print(f"Files: {len(files)}")
    print(f"Chunks: {total_chunks}")
    print(f"Saved: {out_jsonl}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()

