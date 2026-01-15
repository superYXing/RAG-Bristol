import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Try importing rich
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
    from rich.table import Table
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import settings
from core.retriever import rag_retriever
from core.vector_store import vector_store


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _ts_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_log_dir() -> Path:
    d = Path.cwd() / "log"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _build_rerank_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/rerank"


def _parse_rerank_scores(data: Any, expected_len: int) -> List[float]:
    scores = [0.0] * expected_len
    if isinstance(data, dict):
        results = data.get("results")
        if isinstance(results, list):
            for r in results:
                if not isinstance(r, dict):
                    continue
                idx = r.get("index")
                s = r.get("relevance_score")
                if isinstance(idx, int) and 0 <= idx < expected_len:
                    try:
                        scores[idx] = float(s)
                    except Exception:
                        scores[idx] = 0.0
            return scores

        data_list = data.get("data")
        if isinstance(data_list, list):
            for r in data_list:
                if not isinstance(r, dict):
                    continue
                idx = r.get("index")
                s = r.get("relevance_score") or r.get("score")
                if isinstance(idx, int) and 0 <= idx < expected_len:
                    try:
                        scores[idx] = float(s)
                    except Exception:
                        scores[idx] = 0.0
            return scores

    return scores


def _maybe_truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return text
    return text[:max_chars]


async def _rewrite(query: str) -> Tuple[str, float]:
    t0 = time.perf_counter()
    rewritten, _ = await rag_retriever._rewrite_query(query)
    ms = round((time.perf_counter() - t0) * 1000, 2)
    return rewritten, ms


async def _vector_search(query: str, k: int) -> Tuple[List[Dict[str, Any]], float]:
    t0 = time.perf_counter()
    results = await asyncio.to_thread(vector_store.search, query, k)
    ms = round((time.perf_counter() - t0) * 1000, 2)
    candidates: List[Dict[str, Any]] = []
    for hit in results or []:
        candidates.append(
            {
                "content": hit.get("content") or "",
                "metadata": hit.get("metadata") or {},
                "date": hit.get("date"),
                "score": hit.get("score"),
                "id": hit.get("id"),
            }
        )
    return candidates, ms


async def _rerank_local(rewritten_query: str, documents: List[str]) -> Tuple[List[float], float, Optional[str]]:
    t0 = time.perf_counter()
    try:
        scores = await rag_retriever._rerank_local(rewritten_query, documents)
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return [float(s) for s in scores], ms, None
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return [0.0] * len(documents), ms, str(e)


async def _rerank_api(
    base_url: str,
    api_key: str,
    model: str,
    query: str,
    documents: List[str],
    top_n: int,
    timeout_s: float,
) -> Tuple[List[float], float, Optional[str]]:
    url = _build_rerank_url(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "query": query,
        "documents": documents,
        "top_n": min(top_n, len(documents)),
    }

    t0 = time.perf_counter()
    try:
        timeout = httpx.Timeout(timeout_s, connect=min(3.0, timeout_s))
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        scores = _parse_rerank_scores(data, expected_len=len(documents))
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return scores, ms, None
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return [0.0] * len(documents), ms, str(e)


async def main_async(args: argparse.Namespace) -> int:
    rerank_base_url = args.rerank_base_url or settings.OPENAI_BASE_URL
    rerank_api_key = args.rerank_api_key or settings.OPENAI_API_KEY
    rerank_model = args.rerank_model

    if not rerank_base_url:
        raise SystemExit("缺少 rerank base_url：请设置 --rerank-base-url 或 OPENAI_BASE_URL")
    if not rerank_api_key:
        raise SystemExit("缺少 rerank api_key：请设置 --rerank-api-key 或 OPENAI_API_KEY")

    log_dir = _ensure_log_dir()
    run_id = _ts_filename()
    out_path = log_dir / f"benchmark_rerank_api_{run_id}.jsonl"

    records: List[Dict[str, Any]] = []

    use_rich = RICH_AVAILABLE and not args.no_color
    
    if use_rich:
        console = Console()
        console.print(f"[bold cyan]Starting rerank benchmark with {args.n} requests...[/bold cyan]")
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console
        )
        task_id = progress.add_task("[cyan]Processing...", total=args.n)
        progress.start()
    else:
        print(f"Starting rerank benchmark with {args.n} requests...")

    try:
        for i in range(1, args.n + 1):
            t0 = time.perf_counter()
            rewritten, rewrite_ms = await _rewrite(args.query)
            candidates, search_ms = await _vector_search(rewritten, args.k)

            doc_texts = [c.get("content") or "" for c in candidates]
            doc_texts = [_maybe_truncate(t, args.max_doc_chars) for t in doc_texts]
            rewritten_for_rerank = _maybe_truncate(rewritten, args.max_query_chars)

            local_scores, local_ms, local_err = await _rerank_local(rewritten_for_rerank, doc_texts[: args.top_n])
            api_scores, api_ms, api_err = await _rerank_api(
                base_url=rerank_base_url,
                api_key=rerank_api_key,
                model=rerank_model,
                query=rewritten_for_rerank,
                documents=doc_texts[: args.top_n],
                top_n=args.top_n,
                timeout_s=args.timeout,
            )

            total_ms = round((time.perf_counter() - t0) * 1000, 2)

            record = {
                "ts": _now_iso(),
                "run_index": i,
                "query": args.query,
                "rewritten_query": rewritten,
                "counts": {"vector_hits": len(candidates), "rerank_pairs": min(args.top_n, len(doc_texts))},
                "latency_ms": {
                    "rewrite": rewrite_ms,
                    "vector_search": search_ms,
                    "rerank_local": local_ms,
                    "rerank_api": api_ms,
                    "total": total_ms,
                },
                "errors": {"rerank_local": local_err, "rerank_api": api_err},
                "scores_preview": {
                    "local_top3": sorted(local_scores, reverse=True)[:3] if local_scores else [],
                    "api_top3": sorted(api_scores, reverse=True)[:3] if api_scores else [],
                },
            }
            records.append(record)
            
            if use_rich:
                progress.advance(task_id)
            else:
                print(f"[{i}/{args.n}] local_ms={local_ms} api_ms={api_ms} total_ms={total_ms}")
    finally:
        if use_rich:
            progress.stop()

    meta = {
        "type": "benchmark_rerank_api_latency",
        "run_id": run_id,
        "ts": _now_iso(),
        "pipeline": {
            "rewrite": {"base_url": settings.REWRITE_BASE_URL, "model": settings.REWRITE_MODEL_NAME},
            "embedding": {"model": settings.EMBEDDING_MODEL_NAME, "device": "cuda"},
            "rerank_api": {"base_url": rerank_base_url, "model": rerank_model},
        },
        "params": {
            "n": args.n,
            "k": args.k,
            "top_n": args.top_n,"max_doc_chars": args.max_doc_chars,
            "max_query_chars": args.max_query_chars,
            "timeout": args.timeout,
        },
    }

    with out_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"meta": meta}, ensure_ascii=False) + "\n")
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if use_rich:
        console.print(f"[dim]Saved log: {out_path}[/dim]")
        
        table = Table(title="Rerank Benchmark Results", show_header=True, header_style="bold magenta")
        table.add_column("Run", justify="right")
        table.add_column("Local (ms)", justify="right", style="cyan")
        table.add_column("API (ms)", justify="right", style="magenta")
        table.add_column("Total (ms)", justify="right", style="green")
        
        for r in records:
             l = r['latency_ms']
             table.add_row(
                 str(r['run_index']),
                 str(l['rerank_local']),
                 str(l['rerank_api']),
                 str(l['total'])
             )
        console.print(table)
    else:
        print(f"Saved log: {out_path}")

    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--query", default="图书馆几点开门？")
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--k", type=int, default=20, help="向量检索返回数量")
    p.add_argument("--top-n", type=int, default=10, help="参与 rerank 的候选数量")
    p.add_argument("--max-doc-chars", type=int, default=0, help="rerank 文档截断长度，0 表示不截断")
    p.add_argument("--max-query-chars", type=int, default=0, help="rerank query 截断长度，0 表示不截断")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--rerank-base-url", default="", help="yunwuai OpenAI 兼容 base_url（含 /v1）")
    p.add_argument("--rerank-api-key", default="", help="yunwuai key")
    p.add_argument("--rerank-model", default="BAAI/bge-reranker-v2-m3")
    p.add_argument("--no-color", action="store_true", help="Disable colored output")
    return p.parse_args()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    args = parse_args()
    raise SystemExit(asyncio.run(main_async(args)))

