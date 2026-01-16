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
        --bg: #F7F7F5;
        --panel: #FFFFFF;
        --panel-2: #F1F1EE;
        --text: #0B0F19;
        --muted: #5A6476;
        --border: #E6E6E3;
        --accent: #0F766E;
        --danger: #B42318;
        --shadow: 0 10px 30px rgba(11,15,25,0.06);
        --radius: 16px;
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
    }

    div.block-container {
        max-width: 1120px;
        padding-top: 2.0rem;
        padding-bottom: 2.0rem;
        padding-left: 1.25rem;
        padding-right: 1.25rem;
    }

    [data-testid="stSidebar"] {
        background: var(--panel);
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebarContent"] {
        background: #F3F7FF;
    }

    [data-testid="stSidebarUserContent"] {
        background: #F3F7FF;
    }

    h1, h2, h3 {
        letter-spacing: -0.02em;
        color: var(--text);
    }

    .uob-header {
        height: 1px;
        background: var(--border);
        border-radius: 999px;
        margin: 0.5rem 0 1.25rem 0;
    }

    .uob-card {
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--panel);
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
        background: rgba(15, 23, 42, 0.03);
        color: var(--muted);
    }

    .uob-pill--high {
        background: rgba(15, 118, 110, 0.10);
        color: var(--accent);
        border-color: rgba(15, 118, 110, 0.20);
    }

    .uob-pill--mid {
        background: rgba(15, 23, 42, 0.06);
        color: var(--text);
        border-color: rgba(15, 23, 42, 0.10);
    }

    .uob-pill--low {
        background: rgba(180, 35, 24, 0.10);
        color: var(--danger);
        border-color: rgba(180, 35, 24, 0.18);
    }

    .uob-stepper {
        width: 100%;
        padding: 12px 12px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--panel);
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
        background: var(--panel);
        transition: all 260ms ease;
    }

    .uob-step::after {
        content: "";
        position: absolute;
        left: 10px;
        top: 26px;
        width: 2px;
        height: 24px;
        background: var(--border);
        transition: all 260ms ease;
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

    .uob-step.pending .uob-step-label { color: var(--text); }
    .uob-step.pending::before { border-color: var(--border); background: var(--panel); }

    .uob-step.active::before {
        border-color: rgba(15, 118, 110, 0.35);
        background: rgba(15, 118, 110, 0.10);
        box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.08);
    }

    .uob-step.done::before {
        border-color: rgba(15, 118, 110, 0.35);
        background: var(--accent);
    }

    .uob-step.fail::before {
        border-color: rgba(180, 35, 24, 0.35);
        background: var(--danger);
    }

    .uob-step-icon {
        position: absolute;
        left: 0;
        top: 2px;
        width: 22px;
        height: 22px;
        display: grid;
        place-items: center;
        color: var(--muted);
        pointer-events: none;
    }

    .uob-step.active .uob-step-icon { color: var(--accent); }
    .uob-step.done .uob-step-icon,
    .uob-step.fail .uob-step-icon { color: #ffffff; }

    div.stButton > button,
    div.stDownloadButton > button,
    div[data-testid="stBaseButton-secondary"] > button,
    div[data-testid="stBaseButton-primary"] > button {
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
        background: var(--panel) !important;
        color: var(--text) !important;
        padding: 0.56rem 0.80rem !important;
        font-weight: 650 !important;
        letter-spacing: -0.01em;
        box-shadow: none !important;
        transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
    }

    div.stButton > button:hover,
    div.stDownloadButton > button:hover,
    div[data-testid="stBaseButton-secondary"] > button:hover,
    div[data-testid="stBaseButton-primary"] > button:hover {
        border-color: rgba(15, 118, 110, 0.35) !important;
        box-shadow: 0 10px 24px rgba(11,15,25,0.06) !important;
        transform: translateY(-1px);
    }

    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea {
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
        background: var(--panel) !important;
        color: var(--text) !important;
        box-shadow: none !important;
    }

    [data-baseweb="input"] input:focus,
    [data-baseweb="textarea"] textarea:focus {
        border-color: rgba(15,118,110,0.35) !important;
        box-shadow: 0 0 0 4px rgba(15,118,110,0.08) !important;
        outline: none !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        letter-spacing: -0.02em;
    }

    a {
        color: var(--accent);
        text-decoration: none;
    }

    a:hover {
        text-decoration: underline;
    }

    @media (max-width: 980px) {
        .uob-steps { grid-template-columns: repeat(2, 1fr); }
    }

    @media (max-width: 640px) {
        div.block-container {
            padding-top: 1.2rem;
            padding-bottom: 1.5rem;
            padding-left: 0.85rem;
            padding-right: 0.85rem;
        }
        .uob-steps { grid-template-columns: 1fr; }
    }
</style>
""",
        unsafe_allow_html=True,
    )


def _svg_icon(name: str) -> str:
    icons = {
        "check": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
        "x": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg>',
        "spark": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2z"/></svg>',
        "search": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.2-3.2"/></svg>',
        "filter": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16"/><path d="M7 12h10"/><path d="M10 18h4"/></svg>',
        "doc": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/></svg>',
    }
    return icons.get(name, "")


def _stepper_html(active_stage: str, done: List[str], failed_stage: Optional[str]) -> str:
    labels = {
        "rewrite": ("rewrite", "关键词扩写 / 翻译"),
        "retrieve": ("retrieve", "向量检索"),
        "rerank": ("rerank", "重排序"),
        "summary": ("summary", "生成总结"),
    }
    stage_icons = {
        "rewrite": _svg_icon("spark"),
        "retrieve": _svg_icon("search"),
        "rerank": _svg_icon("filter"),
        "summary": _svg_icon("doc"),
    }
    chunks = ['<div class="uob-stepper"><div class="uob-steps">']
    for stage_id, _ in STAGES:
        if failed_stage == stage_id:
            state = "fail"
            icon = _svg_icon("x")
        elif stage_id in done:
            state = "done"
            icon = _svg_icon("check")
        elif stage_id == active_stage:
            state = "active"
            icon = stage_icons.get(stage_id, "")
        else:
            state = "pending"
            icon = stage_icons.get(stage_id, "")
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
    latency_ms: Optional[float] = None
    from_cache: Optional[bool] = None


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
        --accent: #0F766E;
        --text: #0B0F19;
        --muted: #5A6476;
        --border: #E6E6E3;
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
        border-color: rgba(15,118,110,0.35);
        box-shadow: 0 10px 24px rgba(11,15,25,0.06);
        transform: translateY(-1px);
      }}
      .btn.primary {{
        border-color: rgba(15,118,110,0.35);
        color: var(--accent);
      }}
      .content {{
        overflow-wrap: anywhere;
      }}
      .content a {{
        color: var(--accent);
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
        border-color: rgba(15,118,110,0.35);
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

    rerank = doc.rerank_score
    rerank_val = float(rerank) if rerank is not None else None
    rerank_str = f"{rerank_val:.4f}" if rerank_val is not None else "-"
    rerank_cls = "uob-pill"
    preview = (doc.content or "").strip().replace("\n", " ")
    preview = re.sub(r"\s+", " ", preview)[:260]
    title_html = (
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>' if url else title
    )
    return f"""
<div class="uob-card">
  <div style="font-weight:750;color:var(--text);font-size:1.00rem;line-height:1.2rem;">{title_html}</div>
  <div class="uob-kv">
    <span class="{score_cls}">score: {score_str}</span>
    <span class="{rerank_cls}">rerank: {rerank_str}</span>
  </div>
  <div style="margin-top:8px;color:var(--muted);font-size:0.92rem;line-height:1.25rem;">{preview}...</div>
</div>
""".strip()

SAMPLE_QUERIES: List[str] = [
    "图书馆几点关门？",
    "考试周的自习教室开放时间？",
    "如何申请延期完成课程作业？",
    "校园紧急联系人电话是多少？",
    "哪里可以查到最新的考试安排？",
    "如何预约与学业导师的会面？",
    "学生健康中心的开放时间？",
    "交换生项目的申请截止日期？",
    "助学金和奖学金如何申请？",
    "宿舍安静时间有何规定？",
]


def _render_rotating_queries():
    items = json.dumps(SAMPLE_QUERIES, ensure_ascii=False)
    components.html(
        f"""
<div style="margin: 0.25rem 0 1.0rem 0; font-size: 0.86rem; color: var(--muted);">
  <span>示例问题：</span>
  <span id="sample-query" style="font-weight: 500;"></span>
</div>
<script>
  (function() {{
    var items = {items};
    if (!Array.isArray(items) || items.length === 0) return;
    var el = document.getElementById("sample-query");
    if (!el) return;
    var idx = Math.floor(Math.random() * items.length);
    function update() {{
      el.textContent = items[idx];
      idx = (idx + 1) % items.length;
    }}
    update();
    setInterval(update, 4000);
  }})();
</script>
""",
        height=40,
    )


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
    _render_rotating_queries()

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
                if getattr(search_res, "latency_ms", None) is not None:
                    caption = f"检索耗时：{search_res.latency_ms:.2f} ms"
                    if getattr(search_res, "from_cache", None):
                        caption += "（缓存命中）"
                    st.caption(caption)
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
