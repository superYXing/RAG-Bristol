import json
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import streamlit as st

# --- 配置与常量 ---
st.set_page_config(
    page_title="RAG-Bristol Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 布里斯托大学主色调
UOB_RED = "#B01C2E"
BACKEND_PORT = os.getenv("BACKEND_PORT", "8000")
BACKEND_CHAT_URL = os.getenv("BACKEND_CHAT_URL") or f"http://localhost:{BACKEND_PORT}/api/chat"
BACKEND_PIPELINE_URL = os.getenv("BACKEND_PIPELINE_URL") or f"http://localhost:{BACKEND_PORT}/api/pipeline"

# --- 数据结构 ---
@dataclass
class SourceDoc:
    id: int
    content: str
    metadata: Dict[str, Any]
    score: Optional[float] = None

# --- CSS 样式注入 (Vibecoding 核心) ---
def inject_custom_css():
    st.markdown(f"""
        <style>
        /* 全局变量 */
        :root {{
            --uob-red: {UOB_RED};
            --bg-card: #ffffff;
            --text-secondary: #4b5563;
        }}

        /* 1. 侧边栏优化 */
        section[data-testid="stSidebar"] {{
            background-color: #f7f7f9;
            border-right: 1px solid #e5e7eb;
        }}

        section[data-testid="stSidebar"] * {{
            color: #111827;
        }}
        
        /* 侧边栏新建对话按钮 (CTA) */
        .sidebar-cta button {{
            background-color: var(--uob-red) !important;
            color: white !important;
            border-radius: 8px;
            border: none;
            width: 100%;
            height: 45px;
            font-weight: 600;
            transition: all 0.2s ease;
        }}
        .sidebar-cta button:hover {{
            background-color: #8a1624 !important;
            box-shadow: 0 4px 12px rgba(176, 28, 46, 0.3);
        }}

        /* 2. 主内容区 - Hero */
        .hero-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            margin-top: 40px;
            margin-bottom: 40px;
            text-align: center;
        }}
        .hero-title {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: -webkit-linear-gradient(left, #111827, var(--uob-red));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .hero-subtitle {{
            color: var(--text-secondary);
            font-size: 1.1rem;
        }}

        /* 3. 功能卡片网格 (Agent Cards) */
        /* Streamlit的按钮很难完全自定义HTML结构，我们用CSS hack原生按钮 */
        div.stButton > button.agent-card {{
            background-color: var(--bg-card);
            border: 1px solid #e5e7eb;
            color: #111827;
            border-radius: 12px;
            height: 120px;
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            justify-content: center;
            padding: 16px;
            text-align: left;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        div.stButton > button.agent-card:hover {{
            border-color: var(--uob-red);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            color: var(--uob-red);
        }}
        div.stButton > button.agent-card p {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            margin-top: 4px;
            font-weight: 400;
        }}

        /* 4. 推荐胶囊 (Suggestions) */
        div.suggestion-chip > button {{
            border-radius: 999px;
            border: 1px solid #d1d5db;
            background-color: #ffffff;
            color: #111827;
            font-size: 0.85rem;
            padding: 4px 16px;
        }}
        div.suggestion-chip > button:hover {{
            background-color: #f3f4f6;
            border-color: var(--uob-red);
            color: #111827;
        }}

        /* 5. 引用卡片样式 */
        .source-card {{
            background-color: #ffffff;
            border-left: 3px solid var(--uob-red);
            padding: 10px;
            margin-top: 8px;
            margin-bottom: 8px;
            border-radius: 0 8px 8px 0;
            font-size: 0.85rem;
        }}
        .source-card a {{
            color: #7dadff;
            text-decoration: none;
            font-weight: bold;
        }}
        .source-card a:hover {{
            text-decoration: underline;
        }}
        
        /* 隐藏 Streamlit 默认头部 */
        header {{visibility: hidden;}}
        </style>
    """, unsafe_allow_html=True)

# --- 辅助函数 ---

def reset_chat():
    """重置对话状态"""
    st.session_state.messages = []
    st.session_state.chat_started = False
    st.session_state.current_query = ""

def handle_suggestion_click(query_text):
    """处理点击推荐或卡片"""
    st.session_state.current_query = query_text
    st.session_state.chat_started = True
    # 强制重新运行以将 current_query 填入 chat_input (Streamlit 限制，可能无法直接填入，直接发送更流畅)
    # 这里我们采用直接发送的逻辑
    process_user_input(query_text)

def _extract_citations(markdown_text: str) -> List[int]:
    """从文本中提取 [1] [2] 引用编号"""
    nums = set()
    for m in re.finditer(r"\[(\d+)\]", markdown_text):
        try:
            nums.add(int(m.group(1)))
        except ValueError:
            pass
    return sorted(nums)

def _sources_cards_html(sources: List[SourceDoc], cited_indices: List[int]) -> str:
    """生成漂亮的引用卡片 HTML"""
    if not sources:
        return ""
    
    html = "<div style='margin-top: 20px; border-top: 1px solid #444; padding-top: 10px;'><p style='color:#888; font-size:0.9rem;'>📚 参考来源</p>"
    
    # 过滤出被引用的来源，或者显示前3个相关的
    relevant_sources = []
    for s in sources:
        if s.id in cited_indices:
            relevant_sources.append(s)
    
    # 如果没有显式引用，但有检索结果，显示前2个作为相关推荐
    if not relevant_sources and sources:
        relevant_sources = sources[:2]

    for s in relevant_sources:
        # 尝试从 metadata 获取链接和标题
        source_url = s.metadata.get("url") or s.metadata.get("source") or "#"
        # 简单的标题处理
        title = s.metadata.get("title") or Path(str(source_url)).name or "Document"
        
        html += f"""
        <div class="source-card">
            <span style="color: var(--uob-red); font-weight:bold;">[{s.id}]</span>
            <a href="{source_url}" target="_blank">{escape(title)}</a>
            <div style="color: #aaa; font-size: 0.8rem; margin-top: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                {escape(s.content[:150])}...
            </div>
        </div>
        """
    html += "</div>"
    return html

def _stream_chat(query: str):
    """生成器：流式获取后端响应"""
    try:
        with httpx.stream(
            "POST", 
            BACKEND_CHAT_URL, 
            json={"query": query}, 
            timeout=60.0
        ) as response:
            if response.status_code != 200:
                yield f"后端错误: {response.status_code}", []
                return

            full_text = ""
            sources = []
            
            for line in response.iter_lines():
                if not line:
                    continue
                
                # 处理来源元数据
                if line.startswith("__SOURCES__:"):
                    try:
                        json_str = line[len("__SOURCES__:"):]
                        data = json.loads(json_str)
                        # 将 JSON 转换回 SourceDoc 对象
                        sources = [SourceDoc(**item) for item in data]
                    except:
                        pass
                    continue
                
                # 累积文本
                full_text += line
                yield full_text, sources

    except Exception as e:
        yield f"连接错误: {str(e)}", []

def _fetch_pipeline_data(query: str) -> Dict[str, Any]:
    resp = httpx.post(BACKEND_PIPELINE_URL, json={"query": query}, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}

def _render_pipeline_steps(container, steps: List[Dict[str, str]]):
    with container.container():
        cols = st.columns(len(steps))
        for i, step in enumerate(steps):
            with cols[i]:
                st.markdown(f"**{step['label']}**")
                st.caption(step["status"])

def _render_retrieved_docs(container, pipeline_data: Dict[str, Any]):
    top_k = pipeline_data.get("top_k") or []
    timing_ms = pipeline_data.get("timing_ms") or {}
    rewritten_query = pipeline_data.get("rewritten_query") or ""

    with container.container():
        with st.expander("检索与重排结果", expanded=True):
            if rewritten_query:
                st.markdown(f"**Rewritten Query**：{rewritten_query}")
            if timing_ms:
                st.caption(
                    f"rewrite {timing_ms.get('rewrite', 0)} ms · "
                    f"vector_search {timing_ms.get('vector_search', 0)} ms · "
                    f"rerank {timing_ms.get('rerank', 0)} ms · "
                    f"total {timing_ms.get('total', 0)} ms"
                )
            if not top_k:
                st.write("未检索到相关文档。")
                return

            for idx, doc in enumerate(top_k, start=1):
                meta = doc.get("metadata") or {}
                title = meta.get("title") or f"Document {idx}"
                url = meta.get("url") or meta.get("source") or ""
                score = doc.get("score")
                rerank_score = doc.get("rerank_score")
                date = doc.get("date") or meta.get("date") or ""
                content = doc.get("content") or ""

                header_parts = [f"[{idx}] {title}"]
                if date:
                    header_parts.append(str(date))
                if rerank_score is not None:
                    header_parts.append(f"rerank={rerank_score:.4f}" if isinstance(rerank_score, (int, float)) else f"rerank={rerank_score}")
                if score is not None:
                    header_parts.append(f"sim={score:.4f}" if isinstance(score, (int, float)) else f"sim={score}")

                st.markdown(" · ".join(header_parts))
                if url:
                    st.markdown(f"[打开链接]({url})")
                st.markdown(content[:600] + ("..." if len(content) > 600 else ""))
                st.divider()

def process_user_input(user_input: str):
    """处理用户输入的主逻辑"""
    if not user_input:
        return

    st.session_state.chat_started = True
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 强制刷新 UI 以显示用户消息，然后开始生成
    # Streamlit 的执行模型决定了我们需要在下一次重绘时处理生成
    # 但在函数内我们可以直接写 assistant 的占位符

# --- 初始化 Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_started" not in st.session_state:
    st.session_state.chat_started = False
if "current_query" not in st.session_state:
    st.session_state.current_query = ""

# ==========================================
# 页面布局开始
# ==========================================

inject_custom_css()

# --- 1. 左侧侧边栏 (Navigation) ---
with st.sidebar:
    # Logo 区域
    col1, col2 = st.columns([1, 4])
    with col1:
        st.write("🎓") # 这里可以用 st.image 替换为布大 Logo
    with col2:
        st.markdown("<h3 style='margin:0; padding-top:5px;'>RAG-Bristol</h3>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Call to Action: 新建对话
    st.markdown('<div class="sidebar-cta">', unsafe_allow_html=True)
    if st.button("➕ 开启新对话", key="new_chat_btn"):
        reset_chat()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("### 🕒 历史记录")
    # 模拟历史记录 (实际项目中可以存入数据库)
    st.markdown("""
    <div style="color: #888; font-size: 0.9rem; padding-left: 10px;">
        <p>📄 宿舍申请流程</p>
        <p>📄 图书馆开放时间</p>
        <p>📄 计算机学院选课</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    with st.expander("👤 用户设置"):
        st.write("当前模型: Qwen 2.5 (Local)")
        st.write("知识库版本: v2.1")

# --- 2. 右侧主内容区 ---

# 如果还没有开始聊天 (Empty State)
if not st.session_state.chat_started and not st.session_state.messages:
    # Hero Section
    st.markdown("""
        <div class="hero-container">
            <div class="hero-title">Hello, Student 👋</div>
            <div class="hero-subtitle">我是您的布里斯托大学 AI 校园助手，有什么可以帮您？</div>
        </div>
    """, unsafe_allow_html=True)

    # Agent / Feature Grid
    st.markdown("#### 💡 常用功能")
    c1, c2, c3, c4 = st.columns(4)
    
    # 使用 callback 处理点击
    def click_card(prompt):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.chat_started = True
        
    with c1:
        # Hack: 将 button 的 key 设为 distinct，利用 css class "agent-card" 样式化
        if st.button("📚 图书馆服务\n\n查询借阅规则、开放时间和自习室。", key="card_lib"):
            click_card("查找 Arts and Social Sciences Library 的开放时间和借书规则")
            st.rerun()
            
    with c2:
        if st.button("🗺️ 校园地图\n\n寻找 Senate House 或具体教学楼位置。", key="card_map"):
            click_card("Senate House 在哪里？怎么去 Queens Building？")
            st.rerun()

    with c3:
        if st.button("📅 考试与课表\n\n查询考试安排或学期关键日期。", key="card_exam"):
            click_card("2026年第一学期的考试时间表是什么时候？")
            st.rerun()

    with c4:
        if st.button("💻 IT 支持\n\nEduroam 连接指南或软件下载。", key="card_it"):
            click_card("如何连接 Eduroam Wi-Fi？打印机怎么设置？")
            st.rerun()

    # Suggestion Chips
    st.write("") # Spacer
    st.markdown("#### 🎯 试一试")
    
    s1, s2, s3, s4 = st.columns([1, 1, 1, 1])
    # 由于 Streamlit button 无法直接横向紧凑排列，我们使用 columns
    with s1:
        if st.button("住宿费怎么交？", key="sug_1", help="点击发送"):
            click_card("住宿费怎么交？有哪些支付方式？")
            st.rerun()
    with s2:
        if st.button("申请延期提交", key="sug_2"):
            click_card("我有特殊情况，怎么申请作业延期提交 (extenuating circumstances)？")
            st.rerun()
    with s3:
        if st.button("注册校医 GP", key="sug_3"):
            click_card("国际学生如何注册校医 (GP)？")
            st.rerun()

# 如果已经开始聊天 (Chat Flow)
else:
    # 渲染历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                st.markdown(msg["content"])
                # 如果历史消息里存了 sources，也可以在这里渲染
                if "sources" in msg:
                    cards = _sources_cards_html([SourceDoc(**s) for s in msg["sources"]], _extract_citations(msg["content"]))
                    st.markdown(cards, unsafe_allow_html=True)
            else:
                st.markdown(msg["content"])

    # 如果最后一条是用户的，说明需要生成回复 (处理刚从卡片点击进来的情况)
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        with st.chat_message("assistant"):
            pipeline_steps_placeholder = st.empty()
            retrieved_docs_placeholder = st.empty()
            answer_placeholder = st.empty()
            refs_placeholder = st.empty()
            
            final_text = ""
            final_sources = []
            
            # 获取用户最后一条输入
            user_query = st.session_state.messages[-1]["content"]
            
            try:
                steps = [
                    {"id": "retrieve", "label": "Retrieve", "status": "进行中"},
                    {"id": "rerank", "label": "Rerank", "status": "等待中"},
                    {"id": "generate", "label": "Generate", "status": "等待中"},
                ]
                _render_pipeline_steps(pipeline_steps_placeholder, steps)

                pipeline_data = None
                pipeline_rendered = False
                first_token_seen = False

                with ThreadPoolExecutor(max_workers=1) as executor:
                    pipeline_future = executor.submit(_fetch_pipeline_data, user_query)

                    for partial_text, partial_sources in _stream_chat(user_query):
                        if not first_token_seen and partial_text:
                            first_token_seen = True
                            steps = [
                                {"id": "retrieve", "label": "Retrieve", "status": "进行中"},
                                {"id": "rerank", "label": "Rerank", "status": "进行中"},
                                {"id": "generate", "label": "Generate", "status": "进行中"},
                            ]
                            _render_pipeline_steps(pipeline_steps_placeholder, steps)

                        if (not pipeline_rendered) and pipeline_future.done():
                            try:
                                pipeline_data = pipeline_future.result() or {}
                            except Exception:
                                pipeline_data = {}
                            pipeline_rendered = True
                            _render_retrieved_docs(retrieved_docs_placeholder, pipeline_data)
                            steps = [
                                {"id": "retrieve", "label": "Retrieve", "status": "完成"},
                                {"id": "rerank", "label": "Rerank", "status": "完成"},
                                {"id": "generate", "label": "Generate", "status": "进行中"},
                            ]
                            _render_pipeline_steps(pipeline_steps_placeholder, steps)

                        final_text = partial_text
                        final_sources = partial_sources
                        # 实时渲染 Markdown + 光标效果
                        answer_placeholder.markdown(final_text + "▌")
                
                # 完成后移除光标
                answer_placeholder.markdown(final_text)

                if not pipeline_rendered:
                    try:
                        pipeline_data = _fetch_pipeline_data(user_query)
                        pipeline_rendered = True
                        _render_retrieved_docs(retrieved_docs_placeholder, pipeline_data)
                    except Exception:
                        pass
                
                # 渲染引用
                cited_ids = _extract_citations(final_text)
                cards_html = _sources_cards_html(final_sources, cited_ids)
                refs_placeholder.markdown(cards_html, unsafe_allow_html=True)

                steps = [
                    {"id": "retrieve", "label": "Retrieve", "status": "完成"},
                    {"id": "rerank", "label": "Rerank", "status": "完成"},
                    {"id": "generate", "label": "Generate", "status": "完成"},
                ]
                _render_pipeline_steps(pipeline_steps_placeholder, steps)
                
                # 保存助手消息到历史
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_text,
                    "sources": [vars(s) for s in final_sources] # 转 dict 保存
                })
                
            except Exception as e:
                answer_placeholder.markdown(f"❌ 请求出错了: {str(e)}")

# --- 4. 底部输入交互区 ---
# 无论是在 Empty State 还是 Chat Flow，输入框始终在底部
user_input = st.chat_input("向 UoB 助手提问 (例如：我要去哪里领学生卡？)...")

if user_input:
    # 触发状态变更
    st.session_state.chat_started = True
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.rerun()
