"""
benchmark_latency.py - RAG Pipeline End-to-End Latency Benchmark

This script measures the latency of each stage in the RAG pipeline:
- Query rewriting (rewrite)
- Vector search (vector_search)
- Reranking (rerank)
- Time to first token (ttft)
- Full generation (generate)
- Total end-to-end latency (total)

Usage:
    python benchmark_latency.py --queries 10 --output log/

Outputs:
    - JSONL log file with detailed timing for each request
    - Summary statistics table (mean, P50, P95) printed to console
"""

import asyncio
import argparse
import time
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

# Try importing rich
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
    from rich.table import Table
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.retriever import rag_retriever
from core.vector_store import vector_store
from core.generator import rag_generator
from core.config import settings

SOURCES_PREFIX = "__SOURCES__:"

def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")

def _ts_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _ensure_log_dir() -> Path:
    d = Path.cwd() / "log"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    k = (len(xs) - 1) * p
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return float(xs[f])
    d0 = xs[f] * (c - k)
    d1 = xs[c] * (k - f)
    return float(d0 + d1)

async def _rewrite(query: str) -> Tuple[str, float]:
    t0 = time.perf_counter()
    try:
        rewritten_query, _ = await rag_retriever._rewrite_query(query)
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return rewritten_query, ms
    except Exception:
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return query, ms

async def _vector_search(query: str, k: int) -> Tuple[List[Dict[str, Any]], float]:
    t0 = time.perf_counter()
    results = await asyncio.to_thread(vector_store.search, query, k)
    ms = round((time.perf_counter() - t0) * 1000, 2)
    candidates: List[Dict[str, Any]] = []
    for hit in results or []:
        candidates.append(
            {
                "content": hit.get("content"),
                "metadata": hit.get("metadata"),
                "date": hit.get("date"),
                "score": hit.get("score"),
                "id": hit.get("id"),
            }
        )
    return candidates, ms

async def _rerank(query: str, candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], float]:
    if not candidates:
        return candidates, 0.0
    if getattr(rag_retriever, "reranker", None) is None:
        return candidates, 0.0
    t0 = time.perf_counter()
    doc_texts = [c.get("content") or "" for c in candidates]
    scores = await rag_retriever._rerank_local(query, doc_texts)
    for i, score in enumerate(scores):
        candidates[i]["rerank_score"] = score
    candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    ms = round((time.perf_counter() - t0) * 1000, 2)
    return candidates, ms

async def _generate(query: str, docs: List[Dict[str, Any]]) -> Tuple[str, float, float, int, int]:
    t0 = time.perf_counter()
    first_token_ms: Optional[float] = None
    sources_json: Optional[str] = None
    text_parts: List[str] = []
    async for chunk in rag_generator.generate_stream(query, docs):
        if chunk.startswith(SOURCES_PREFIX):
            sources_json = chunk[len(SOURCES_PREFIX) :].strip()
            continue
        if first_token_ms is None and chunk:
            first_token_ms = round((time.perf_counter() - t0) * 1000, 2)
        text_parts.append(chunk)
    total_ms = round((time.perf_counter() - t0) * 1000, 2)
    text = "".join(text_parts)
    sources_count = 0
    if sources_json:
        try:
            sources_count = len(json.loads(sources_json))
        except Exception:
            sources_count = 0
    return text, (first_token_ms or 0.0), total_ms, len(text), sources_count

async def _run_once(query: str, top_k: int, run_index: int) -> Dict[str, Any]:
    t0 = time.perf_counter()
    rewritten, rewrite_ms = await _rewrite(query)
    candidates, search_ms = await _vector_search(rewritten, top_k)
    candidates, rerank_ms = await _rerank(rewritten, candidates)
    top_docs = candidates[:5]
    answer, ttft_ms, gen_ms, answer_chars, sources_count = await _generate(query, top_docs)
    total_ms = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "ts": _now_iso(),
        "run_index": run_index,
        "query": query,
        "rewritten_query": rewritten,
        "docs": {"vector_hits": len(candidates), "used": len(top_docs), "sources_count": sources_count},
        "latency_ms": {
            "rewrite": rewrite_ms,
            "vector_search": search_ms,
            "rerank": rerank_ms,
            "ttft": ttft_ms,
            "generate": gen_ms,
            "total": total_ms,
        },
        "answer": {"chars": answer_chars, "preview": answer[:300]},
    }

def _summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _vals(key: str) -> List[float]:
        out: List[float] = []
        for r in records:
            v = r.get("latency_ms", {}).get(key)
            if isinstance(v, (int, float)):
                out.append(float(v))
        return out

    metrics = ["rewrite", "vector_search", "rerank", "ttft", "generate", "total"]
    summary: Dict[str, Any] = {}
    for m in metrics:
        xs = _vals(m)
        summary[m] = {
            "count": len(xs),
            "mean": round(mean(xs), 2) if xs else 0.0,
            "p50": round(_percentile(xs, 0.50), 2) if xs else 0.0,
            "p95": round(_percentile(xs, 0.95), 2) if xs else 0.0,
        }
    return summary

async def main_async(args: argparse.Namespace) -> int:
    log_dir = _ensure_log_dir()
    run_id = _ts_filename()
    out_path = log_dir / f"benchmark_latency_{run_id}.jsonl"

    meta = {
        "type": "benchmark_latency",
        "run_id": run_id,
        "ts": _now_iso(),
        "models": {
            "rewrite": {"base_url": settings.REWRITE_BASE_URL, "model": settings.REWRITE_MODEL_NAME},
            "embedding": {"model": settings.EMBEDDING_MODEL_NAME, "device": "cuda"},
            "reranker": {"model": settings.RERANKER_MODEL_NAME, "enabled": bool(getattr(rag_retriever, "reranker", None))},
            "generate": {"base_url": settings.GENERATE_BASE_URL, "model": settings.GENERATE_MODEL_NAME},
        },
        "params": {"n": args.n, "top_k": args.top_k, "concurrency": args.concurrency},
    }

    records: List[Dict[str, Any]] = []
    sem = asyncio.Semaphore(args.concurrency)
    
    use_rich = RICH_AVAILABLE and not args.no_color

    async def _guarded(i: int, progress_ctx=None, task_id=None) -> None:
        async with sem:
            try:
                r = await _run_once(args.query, args.top_k, i)
            except Exception as e:
                r = {"ts": _now_iso(), "run_index": i, "query": args.query, "error": str(e)}
            records.append(r)
            
            total_ms = r.get('latency_ms', {}).get('total')
            err = r.get('error')
            
            if use_rich and progress_ctx:
                progress_ctx.advance(task_id)
                if err:
                    progress_ctx.console.print(f"[red]Run {i} failed: {err}[/red]")
            else:
                print(f"[{i}/{args.n}] total_ms={total_ms} error={err}")

    if use_rich:
        console = Console()
        console.print(f"[bold cyan]Starting benchmark with {args.n} requests (concurrency={args.concurrency})...[/bold cyan]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Processing...", total=args.n)
            tasks = [asyncio.create_task(_guarded(i, progress, task)) for i in range(1, args.n + 1)]
            await asyncio.gather(*tasks)
    else:
        print(f"Starting benchmark with {args.n} requests (concurrency={args.concurrency})...")
        tasks = [asyncio.create_task(_guarded(i)) for i in range(1, args.n + 1)]
        await asyncio.gather(*tasks)

    summary = _summary([r for r in records if "latency_ms" in r])

    with out_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"meta": meta}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
        for r in sorted(records, key=lambda x: x.get("run_index", 0)):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if use_rich:
        console = Console()
        console.print(f"[dim]Saved log: {out_path}[/dim]")
        
        table = Table(title="Benchmark Latency Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Mean (ms)", justify="right", style="green")
        table.add_column("P50 (ms)", justify="right", style="yellow")
        table.add_column("P95 (ms)", justify="right", style="red")
        
        for metric, stats in summary.items():
            table.add_row(
                metric,
                str(stats['count']),
                str(stats['mean']),
                str(stats['p50']),
                str(stats['p95'])
            )
        console.print(table)
    else:
        print(f"Saved log: {out_path}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        
    return 0

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--query", default="图书馆几点开门？")
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--no-color", action="store_true", help="Disable colored output")
    return p.parse_args()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    args = parse_args()
    raise SystemExit(asyncio.run(main_async(args)))
