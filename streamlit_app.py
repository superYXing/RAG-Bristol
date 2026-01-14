import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except Exception:
    get_script_run_ctx = None

try:
    from pydantic import BaseModel, Field, ValidationError
except Exception:
    BaseModel = object  # type: ignore
    Field = lambda *args, **kwargs: None  # type: ignore
    ValidationError = Exception  # type: ignore

if __name__ == "__main__" and get_script_run_ctx is not None and get_script_run_ctx() is None:
    print("检测到你在用 `python streamlit_app.py` 运行 Streamlit。")
    print("请改用：")
    print("  streamlit run .\\streamlit_app.py")
    sys.exit(0)

st.set_page_config(page_title="校园智能助手", layout="wide", initial_sidebar_state="expanded")


STAGES: List[Tuple[str, str]] = [
    ("rewrite", "rewrite"),
    ("retrieve", "retrieve"),
    ("rerank", "rerank"),
    ("summary", "summary"),
]

def uuid4_hex() -> str:
    import uuid

    return uuid.uuid4().hex


def _inject_css():
    st.markdown(
        """
<style>
    :root {
        --uob-red: #B01C2E;
        --uob-red-2: #D32F2F;
        --bg: #ffffff;
        --panel: #F7F7F9;
        --text: #111827;
        --muted: #6B7280;
        --border: #E5E7EB;
        --shadow: 0 10px 30px rgba(17,24,39,0.08);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FFF5F5 0%, #FFFFFF 100%);
        border-right: 1px solid #F1C9CF;
    }

    h1, h2, h3 {
        letter-spacing: -0.02em;
        color: var(--text);
    }

    .uob-header {
        height: 5px;
        border-radius: 8px;
        background: linear-gradient(90deg, var(--uob-red) 0%, #FFCDD2 60%, #FFFFFF 100%);
        margin: 6px 0 18px 0;
    }

    .uob-card {
        border: 1px solid var(--border);
        border-radius: 14px;
        background: white;
        box-shadow: var(--shadow);
        padding: 14px 14px;
    }

    .uob-kv {
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
        color: var(--muted);
        font-size: 0.92rem;
        margin-top: 6px;
    }

    .uob-pill {
        display: inline-flex;
        align-items: center;
        padding: 3px 10px;
        border-radius: 999px;
        font-weight: 750;
        font-size: 0.86rem;
        letter-spacing: 0.01em;
        border: 1px solid var(--border);
    }

    .uob-pill--high {
        background: rgba(16, 185, 129, 0.10);
        color: #047857;
        border-color: rgba(16, 185, 129, 0.25);
    }

    .uob-pill--mid {
        background: rgba(245, 158, 11, 0.12);
        color: #92400E;
        border-color: rgba(245, 158, 11, 0.30);
    }

    .uob-pill--low {
        background: rgba(239, 68, 68, 0.10);
        color: #B91C1C;
        border-color: rgba(239, 68, 68, 0.25);
    }

    .uob-stepper {
        width: 100%;
        padding: 12px 12px;
        border: 1px solid var(--border);
        border-radius: 14px;
        background: linear-gradient(180deg, #FFFFFF 0%, #FAFAFB 100%);
        box-shadow: var(--shadow);
    }

    .uob-steps {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        align-items: start;
    }

    .uob-step {
        position: relative;
        padding-left: 34px;
        min-height: 36px;
    }

    .uob-step::before {
        content: "";
        position: absolute;
        left: 0;
        top: 3px;
        width: 22px;
        height: 22px;
        border-radius: 999px;
        border: 2px solid var(--border);
        background: white;
        transition: all 320ms ease;
    }

    .uob-step::after {
        content: "";
        position: absolute;
        left: 10px;
        top: 26px;
        width: 2px;
        height: 24px;
        background: var(--border);
        transition: all 320ms ease;
    }

    .uob-step:last-child::after {
        display: none;
    }

    .uob-step-label {
        font-weight: 650;
        color: var(--text);
        font-size: 0.95rem;
        line-height: 1.1rem;
    }

    .uob-step-sub {
        margin-top: 3px;
        font-size: 0.82rem;
        color: var(--muted);
        line-height: 1.05rem;
    }

    .uob-step.pending .uob-step-label { color: #374151; }
    .uob-step.pending::before { border-color: var(--border); background: white; }

    .uob-step.active::before {
        border-color: transparent;
        background: linear-gradient(135deg, #2563EB 0%, #22C55E 45%, #F59E0B 72%, #EF4444 100%);
        box-shadow: 0 0 0 4px rgba(176,28,46,0.10);
        animation: uobPulse 2s ease-in-out infinite;
    }

    .uob-step.done::before {
        border-color: transparent;
        background: linear-gradient(135deg, #10B981 0%, #22C55E 100%);
    }

    .uob-step.fail::before {
        border-color: transparent;
        background: linear-gradient(135deg, #EF4444 0%, #F97316 100%);
    }

    .uob-step-icon {
        position: absolute;
        left: 0;
        top: 2px;
        width: 22px;
        height: 22px;
        display: grid;
        place-items: center;
        color: white;
        font-size: 0.85rem;
        font-weight: 800;
        pointer-events: none;
    }

    @keyframes uobPulse {
        0%, 100% { transform: scale(1); filter: saturate(1); }
        50% { transform: scale(1.03); filter: saturate(1.15); }
    }
</style>
""",
        unsafe_allow_html=True,
    )


def _stepper_html(active_stage: str, done: List[str], failed_stage: Optional[str]) -> str:
    labels = {
        "rewrite": ("rewrite", "关键词扩写 / 翻译"),
        "retrieve": ("retrieve", "向量检索"),
        "rerank": ("rerank", "重排序"),
        "summary": ("summary", "生成总结"),
    }
    chunks = ['<div class="uob-stepper"><div class="uob-steps">']
    for stage_id, _ in STAGES:
        if failed_stage == stage_id:
            state = "fail"
            icon = "✗"
        elif stage_id in done:
            state = "done"
            icon = "✓"
        elif stage_id == active_stage:
            state = "active"
            icon = ""
        else:
            state = "pending"
            icon = ""
        title, sub = labels[stage_id]
        chunks.append(
            f"""
<div class="uob-step {state}">
  <div class="uob-step-icon">{icon}</div>
  <div class="uob-step-label">{title}</div>
  <div class="uob-step-sub">{sub}</div>
</div>
""".strip()
        )
    chunks.append("</div></div>")
    return "\n".join(chunks)


class _SearchHit(BaseModel):  # type: ignore[misc]
    id: Optional[str] = None
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)  # type: ignore[assignment]
    date: Optional[str] = None
    score: Optional[float] = None
    rerank_score: Optional[float] = None


class _SearchResponse(BaseModel):  # type: ignore[misc]
    results: List[_SearchHit]


class _SourceDoc(BaseModel):  # type: ignore[misc]
    id: int
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)  # type: ignore[assignment]
    score: Optional[float] = None
    date: Optional[str] = None


def _post_json_with_retry(
    url: str,
    payload: Dict[str, Any],
    timeout_s: float,
    max_retries: int,
) -> Dict[str, Any]:
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, timeout=timeout_s)
            if 200 <= resp.status_code < 300:
                data = resp.json()
                if not isinstance(data, dict):
                    raise ValueError("响应不是 JSON 对象")
                return data
            if resp.status_code in (408, 429) or 500 <= resp.status_code < 600:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        except Exception as e:
            last_exc = e
            if attempt == max_retries - 1:
                break
            time.sleep(min(1.6, 0.25 * (2**attempt) + random.random() * 0.15))
    raise last_exc or RuntimeError("请求失败")


def _iter_stream_with_retry(
    url: str,
    payload: Dict[str, Any],
    timeout_s: float,
    max_retries: int,
) -> Iterable[str]:
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        received_any = False
        try:
            resp = requests.post(
                url,
                json=payload,
                stream=True,
                timeout=(min(3.0, timeout_s), timeout_s),
            )
            if not (200 <= resp.status_code < 300):
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            for chunk in resp.iter_content(chunk_size=2048, decode_unicode=True):
                if not chunk:
                    continue
                received_any = True
                yield chunk
            return
        except Exception as e:
            last_exc = e
            if received_any or attempt == max_retries - 1:
                break
            time.sleep(min(1.6, 0.25 * (2**attempt) + random.random() * 0.15))
    raise last_exc or RuntimeError("流式请求失败")


def _render_markdown_enhanced(md: str, key: str):
    md_json = json.dumps(md)
    height = max(260, min(980, 260 + int(len(md) / 6)))
    components.html(
        f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11.11.1/styles/github.min.css" />
    <script src="https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/highlight.js@11.11.1/lib/highlight.min.js"></script>
    <style>
      :root {{
        --uob-red: #B01C2E;
        --text: #111827;
        --muted: #6B7280;
        --border: #E5E7EB;
      }}
      body {{
        margin: 0;
        background: transparent;
        color: var(--text);
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Symbol";
      }}
      .wrap {{
        border: 1px solid var(--border);
        border-radius: 14px;
        background: white;
        padding: 14px 14px 10px 14px;
        animation: fadeIn 420ms ease both;
      }}
      @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(6px); }}
        to {{ opacity: 1; transform: translateY(0); }}
      }}
      .topbar {{
        display: flex;
        justify-content: flex-end;
        gap: 8px;
        margin-bottom: 10px;
      }}
      .btn {{
        border: 1px solid var(--border);
        background: white;
        color: var(--text);
        border-radius: 10px;
        padding: 6px 10px;
        font-size: 12px;
        cursor: pointer;
        transition: all 220ms ease;
      }}
      .btn:hover {{
        border-color: rgba(176,28,46,0.5);
        box-shadow: 0 6px 18px rgba(17,24,39,0.08);
        transform: translateY(-1px);
      }}
      .btn.primary {{
        border-color: rgba(176,28,46,0.5);
        color: var(--uob-red);
      }}
      .content {{
        overflow-wrap: anywhere;
      }}
      .content a {{
        color: var(--uob-red);
        text-decoration: none;
      }}
      .content a:hover {{
        text-decoration: underline;
      }}
      pre {{
        position: relative;
        padding-top: 30px;
        border-radius: 12px;
        border: 1px solid var(--border);
        overflow: auto;
      }}
      pre code {{
        font-size: 13px;
      }}
      .codebtn {{
        position: absolute;
        top: 6px;
        right: 8px;
        border: 1px solid var(--border);
        background: white;
        border-radius: 9px;
        padding: 4px 8px;
        font-size: 12px;
        cursor: pointer;
        transition: all 220ms ease;
      }}
      .codebtn:hover {{
        border-color: rgba(176,28,46,0.5);
        transform: translateY(-1px);
      }}
      @media (max-width: 640px) {{
        .wrap {{ padding: 12px 10px; }}
      }}
    </style>
  </head>
  <body>
    <div class="wrap" id="{key}">
      <div class="topbar">
        <button class="btn primary" id="{key}-copyAll">复制全文</button>
      </div>
      <div class="content" id="{key}-content"></div>
    </div>
    <script>
      const mdText = {md_json};
      const md = window.markdownit({{ html: false, linkify: true, breaks: true }});
      const root = document.getElementById("{key}-content");
      root.innerHTML = md.render(mdText);

      root.querySelectorAll("pre code").forEach((block) => {{
        try {{ window.hljs.highlightElement(block); }} catch (e) {{}}
      }});

      root.querySelectorAll("pre").forEach((pre) => {{
        const code = pre.querySelector("code");
        if (!code) return;
        const btn = document.createElement("button");
        btn.className = "codebtn";
        btn.textContent = "复制";
        btn.addEventListener("click", async () => {{
          try {{
            await navigator.clipboard.writeText(code.innerText);
            btn.textContent = "已复制";
            setTimeout(() => btn.textContent = "复制", 1200);
          }} catch (e) {{
            btn.textContent = "失败";
            setTimeout(() => btn.textContent = "复制", 1200);
          }}
        }});
        pre.appendChild(btn);
      }});

      document.getElementById("{key}-copyAll").addEventListener("click", async () => {{
        const btn = document.getElementById("{key}-copyAll");
        try {{
          await navigator.clipboard.writeText(mdText);
          btn.textContent = "已复制";
          setTimeout(() => btn.textContent = "复制全文", 1200);
        }} catch (e) {{
          btn.textContent = "失败";
          setTimeout(() => btn.textContent = "复制全文", 1200);
        }}
      }});
    </script>
  </body>
</html>
""",
        height=height,
        scrolling=True,
    )


def _format_doc_card(doc: _SearchHit) -> str:
    meta = doc.metadata or {}
    title = str(meta.get("title") or "无标题")
    url = str(meta.get("url") or "").strip()
    score = doc.score
    score_val = float(score) if score is not None else None
    score_str = f"{score_val:.4f}" if score_val is not None else "-"
    if score_val is None:
        score_cls = "uob-pill"
    elif score_val >= 0.80:
        score_cls = "uob-pill uob-pill--high"
    elif score_val >= 0.65:
        score_cls = "uob-pill uob-pill--mid"
    else:
        score_cls = "uob-pill uob-pill--low"
    preview = (doc.content or "").strip().replace("\n", " ")
    preview = re.sub(r"\s+", " ", preview)[:260]
    title_html = (
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>' if url else title
    )
    return f"""
<div class="uob-card">
  <div style="font-weight:750;color:#111827;font-size:1.00rem;line-height:1.2rem;">{title_html}</div>
  <div class="uob-kv">
    <span class="{score_cls}">score: {score_str}</span>
  </div>
  <div style="margin-top:8px;color:#374151;font-size:0.92rem;line-height:1.25rem;">{preview}...</div>
</div>
""".strip()


_inject_css()

def _history_file_path() -> Path:
    base_dir = Path(__file__).resolve().parent / ".streamlit"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "chat_history.json"


def _load_history() -> List[Dict[str, Any]]:
    p = _history_file_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        return []
    return []


def _save_history(items: List[Dict[str, Any]]) -> None:
    p = _history_file_path()
    p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_title_from_messages(messages: List[Dict[str, Any]]) -> str:
    for m in messages:
        if m.get("role") == "user":
            s = str(m.get("content") or "").strip()
            if s:
                return (s[:26] + "…") if len(s) > 26 else s
    return "未命名会话"


def _ensure_session_state():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = _load_history()
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = uuid4_hex()
    if "doc_modal_open" not in st.session_state:
        st.session_state.doc_modal_open = False
    if "selected_doc" not in st.session_state:
        st.session_state.selected_doc = None


def _persist_current_session():
    session_id = st.session_state.current_session_id
    messages = st.session_state.messages
    title = _make_title_from_messages(messages)
    now = datetime.now().isoformat(timespec="seconds")

    items: List[Dict[str, Any]] = st.session_state.chat_history
    existing = None
    for it in items:
        if it.get("id") == session_id:
            existing = it
            break
    if existing is None:
        existing = {"id": session_id, "created_at": now}
        items.insert(0, existing)
    existing["updated_at"] = now
    existing["title"] = title
    existing["messages"] = messages
    st.session_state.chat_history = items
    _save_history(items)


def _start_new_chat():
    st.session_state.current_session_id = uuid4_hex()
    st.session_state.messages = [{"role": "assistant", "content": "你好，我是校园智能助手。请输入你的问题。"}]
    _persist_current_session()


def _open_doc_modal(doc: _SearchHit):
    st.session_state.selected_doc = doc.model_dump()  # type: ignore[attr-defined]
    st.session_state.doc_modal_open = True
    st.rerun()


def _render_doc_modal():
    if not st.session_state.doc_modal_open:
        return
    raw = st.session_state.selected_doc
    if not isinstance(raw, dict):
        st.session_state.doc_modal_open = False
        return
    try:
        doc = _SearchHit.model_validate(raw)  # type: ignore[attr-defined]
    except Exception:
        st.session_state.doc_modal_open = False
        return

    title = str((doc.metadata or {}).get("title") or "文档内容")
    url = str((doc.metadata or {}).get("url") or "").strip()
    header = title if not url else f"[{title}]({url})"
    content = doc.content or ""

    if hasattr(st, "dialog"):
        @st.dialog("文档详情")
        def _dlg():
            st.markdown(header)
            copy_key = f"doc_copy_{uuid4_hex()}"
            components.html(
                f"""
<div style="display:flex;gap:8px;justify-content:flex-end;margin:6px 0 10px 0;">
  <button id="{copy_key}" style="border:1px solid #E5E7EB;background:#fff;border-radius:10px;padding:6px 10px;cursor:pointer;">复制内容</button>
</div>
<pre style="white-space:pre-wrap;word-break:break-word;border:1px solid #E5E7EB;border-radius:12px;padding:12px;max-height:420px;overflow:auto;margin:0;">{json.dumps(content)[1:-1]}</pre>
<script>
  const btn = document.getElementById("{copy_key}");
  btn.addEventListener("click", async () => {{
    try {{
      await navigator.clipboard.writeText({json.dumps(content)});
      btn.textContent = "已复制";
      setTimeout(() => btn.textContent = "复制内容", 1200);
    }} catch (e) {{
      btn.textContent = "失败";
      setTimeout(() => btn.textContent = "复制内容", 1200);
    }}
  }});
</script>
""",
                height=520,
                scrolling=True,
            )
            if st.button("关闭", use_container_width=True):
                st.session_state.doc_modal_open = False
                st.session_state.selected_doc = None
                st.rerun()

        _dlg()
    else:
        with st.expander("文档详情", expanded=True):
            st.markdown(header)
            st.text_area("内容", value=content, height=360)
            if st.button("关闭", use_container_width=True):
                st.session_state.doc_modal_open = False
                st.session_state.selected_doc = None
                st.rerun()


def _render_docs_interactive(docs: List[_SearchHit], scope: str):
    for i, d in enumerate(docs):
        st.markdown(_format_doc_card(d), unsafe_allow_html=True)
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("查看全文", key=f"open_{scope}_{i}", use_container_width=True):
                _open_doc_modal(d)
        with c2:
            u = str((d.metadata or {}).get("url") or "").strip()
            if u:
                if hasattr(st, "link_button"):
                    st.link_button("打开链接", u, use_container_width=True)
                else:
                    st.markdown(f"[打开链接]({u})")


_ensure_session_state()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "你好，我是校园智能助手。请输入你的问题。"}]
    _persist_current_session()

if "backend_url" not in st.session_state:
    st.session_state.backend_url = "http://localhost:8000"

st.markdown('<div class="uob-header"></div>', unsafe_allow_html=True)
header_left, header_right = st.columns([1, 9], vertical_alignment="center")
with header_left:
    st.image(
        "asserts\logo.png",
        width=54,
    )
with header_right:
    st.title("Campus AI Assistant")

with st.sidebar:
    st.subheader("设置")
    st.session_state.backend_url = st.text_input("后端地址", value=st.session_state.backend_url)
    show_debug = st.toggle("显示调试信息", value=False)
    if st.button("新会话", use_container_width=True):
        _start_new_chat()
        st.rerun()
    if st.button("清空当前对话", use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": "你好，我是校园智能助手。请输入你的问题。"}]
        _persist_current_session()
        st.rerun()

    st.markdown("---")
    st.subheader("历史会话")
    history_items: List[Dict[str, Any]] = st.session_state.chat_history
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for it in history_items:
        ts = str(it.get("updated_at") or it.get("created_at") or "")
        day = ts[:10] if len(ts) >= 10 else "unknown"
        grouped.setdefault(day, []).append(it)

    for day in sorted(grouped.keys(), reverse=True):
        with st.expander(day, expanded=False):
            for it in grouped[day]:
                sid = str(it.get("id") or "")
                title = str(it.get("title") or "未命名会话")
                if st.button(title, key=f"hist_{sid}", use_container_width=True):
                    msgs = it.get("messages")
                    if isinstance(msgs, list):
                        st.session_state.current_session_id = sid
                        st.session_state.messages = msgs
                        st.rerun()


for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            _render_markdown_enhanced(message.get("content") or "", key=f"md_hist_{i}")
            docs = message.get("docs") or []
            if docs:
                with st.expander(f"检索结果 ({len(docs)})", expanded=False):
                    parsed_docs: List[_SearchHit] = []
                    for d in docs:
                        if isinstance(d, dict):
                            try:
                                parsed_docs.append(_SearchHit.model_validate(d))  # type: ignore[attr-defined]
                            except Exception:
                                continue
                    _render_docs_interactive(parsed_docs, scope=f"hist_{i}")
        else:
            st.markdown(message.get("content") or "")

_render_doc_modal()


def _call_search(base_url: str, query: str) -> _SearchResponse:
    url = base_url.rstrip("/") + "/api/search"
    raw = _post_json_with_retry(url, {"query": query}, timeout_s=5.0, max_retries=3)
    try:
        return _SearchResponse.model_validate(raw)  # type: ignore[attr-defined]
    except Exception as e:
        raise RuntimeError(f"API 响应校验失败：{e}")


def _extract_sources_and_text(stream_chunks: Iterable[str]) -> Tuple[List[_SourceDoc], str]:
    buffer = ""
    sources: List[_SourceDoc] = []
    answer_parts: List[str] = []

    for chunk in stream_chunks:
        buffer += chunk
        while True:
            if buffer.startswith("__SOURCES__:"):
                nl = buffer.find("\n")
                if nl == -1:
                    break
                head = buffer[:nl]
                buffer = buffer[nl + 1 :]
                _, _, json_part = head.partition(":")
                try:
                    parsed = json.loads(json_part)
                    if isinstance(parsed, list):
                        sources = [_SourceDoc.model_validate(x) for x in parsed]  # type: ignore[attr-defined]
                except Exception:
                    sources = []
                continue
            break
        if buffer:
            answer_parts.append(buffer)
            buffer = ""

    return sources, "".join(answer_parts)


if prompt := st.chat_input("请输入你的问题，例如：图书馆几点关门？"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    _persist_current_session()
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        stepper_box = st.empty()
        docs_box = st.empty()
        answer_box = st.empty()

        active = "rewrite"
        done: List[str] = []
        failed: Optional[str] = None
        stepper_box.markdown(_stepper_html(active, done, failed), unsafe_allow_html=True)

        base_url = st.session_state.backend_url.strip()
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_call_search, base_url, prompt)

        last_switch = time.monotonic()
        stage_order = ["rewrite", "retrieve", "rerank"]
        stage_index = 0
        while not future.done():
            now = time.monotonic()
            if now - last_switch >= 2.0:
                stage_index = (stage_index + 1) % len(stage_order)
                active = stage_order[stage_index]
                stepper_box.markdown(_stepper_html(active, done, failed), unsafe_allow_html=True)
                last_switch = now
            time.sleep(0.08)

        try:
            search_res = future.result()
        except Exception as e:
            failed = active
            stepper_box.markdown(_stepper_html(active, done, failed), unsafe_allow_html=True)
            answer_box.error(f"检索失败：{e}")
            st.session_state.messages.append(
                {"role": "assistant", "content": f"检索失败：{e}", "docs": []}
            )
            _persist_current_session()
            st.stop()
        finally:
            executor.shutdown(wait=False, cancel_futures=False)

        docs = search_res.results or []
        done = ["rewrite", "retrieve"]
        active = "rerank"
        stepper_box.markdown(_stepper_html(active, done, failed), unsafe_allow_html=True)

        with docs_box.container():
            if not docs:
                st.warning("未检索到相关文档，将直接返回空结果。")
            else:
                st.markdown(f"**检索结果：{len(docs)} 条**")
                cols = st.columns(2)
                for idx, d in enumerate(docs):
                    with cols[idx % 2]:
                        st.markdown(_format_doc_card(d), unsafe_allow_html=True)
                        c1, c2 = st.columns([1, 1])
                        with c1:
                            if st.button("查看全文", key=f"open_live_{idx}", use_container_width=True):
                                _open_doc_modal(d)
                        with c2:
                            u = str((d.metadata or {}).get("url") or "").strip()
                            if u:
                                if hasattr(st, "link_button"):
                                    st.link_button("打开链接", u, use_container_width=True)
                                else:
                                    st.markdown(f"[打开链接]({u})")

        done = ["rewrite", "retrieve", "rerank"]
        active = "summary"
        stepper_box.markdown(_stepper_html(active, done, failed), unsafe_allow_html=True)

        summarize_url = base_url.rstrip("/") + "/api/summarize"
        summarize_payload = {"query": prompt, "docs": [d.model_dump() for d in docs]}  # type: ignore[attr-defined]

        try:
            sources: List[_SourceDoc] = []
            sources_parsed = False
            pending = ""
            answer_text = ""

            last_render = time.monotonic()
            for chunk in _iter_stream_with_retry(
                summarize_url,
                summarize_payload,
                timeout_s=20.0,
                max_retries=2,
            ):
                pending += chunk
                while not sources_parsed and pending.startswith("__SOURCES__:"):
                    nl = pending.find("\n")
                    if nl == -1:
                        break
                    head = pending[:nl]
                    pending = pending[nl + 1 :]
                    _, _, json_part = head.partition(":")
                    try:
                        parsed = json.loads(json_part)
                        if isinstance(parsed, list):
                            sources = [_SourceDoc.model_validate(x) for x in parsed]  # type: ignore[attr-defined]
                    except Exception:
                        sources = []
                    sources_parsed = True

                if pending and not pending.startswith("__SOURCES__:"):
                    answer_text += pending
                    pending = ""

                now = time.monotonic()
                if now - last_render >= 0.08:
                    answer_box.markdown(answer_text + "▌")
                    last_render = now

            answer_box.markdown(answer_text)

            if show_debug and sources:
                with st.expander("调试：sources", expanded=False):
                    st.json([s.model_dump() for s in sources])  # type: ignore[attr-defined]

            answer_box.empty()
            _render_markdown_enhanced(answer_text, key=f"md_live_{uuid4_hex()}")

            done = ["rewrite", "retrieve", "rerank", "summary"]
            active = "summary"
            stepper_box.markdown(_stepper_html(active, done, failed), unsafe_allow_html=True)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer_text,
                    "docs": [d.model_dump() for d in docs],  # type: ignore[attr-defined]
                    "sources": [s.model_dump() for s in sources],  # type: ignore[attr-defined]
                }
            )
            _persist_current_session()
        except Exception as e:
            failed = "summary"
            stepper_box.markdown(_stepper_html(active, done, failed), unsafe_allow_html=True)
            answer_box.error(f"总结失败：{e}")
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"总结失败：{e}",
                    "docs": [d.model_dump() for d in docs],  # type: ignore[attr-defined]
                    "sources": [],
                }
            )
            _persist_current_session()
