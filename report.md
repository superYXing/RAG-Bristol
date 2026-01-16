# RAG-Bristol 项目开发与问题修复报告

本报告总结了本次开发会话中完成的主要功能更新、遇到的问题及其解决方案。

## 1. 新增功能 (New Features)

### 1.1 文档摘要接口 (`/api/summarize`)
*   **需求**: 提供一个不经过检索重排序，直接对输入文档进行总结的流式接口。
*   **实现**: 
    *   在 `backend/app.py` 中新增 `SummarizeRequest` 数据模型。
    *   实现 `@app.post("/api/summarize")` 路由，直接调用 `rag_generator.generate_stream`。
*   **状态**: 已完成并验证。
*   **相关文件**: [backend/app.py](backend/app.py)

### 1.2 严格链接过滤机制 (`Link Filter`)
*   **需求**: 在数据入库（Ingest）阶段，移除正文中的所有链接（HTML、Markdown、纯文本 URL），但必须保留元数据中的链接。
*   **实现**:
    *   创建独立模块 `backend/core/link_filter.py`，使用正则表达式处理三种链接格式。
    *   集成到 `backend/core/ingest.py` 的 `DocumentProcessor` 中。
*   **关键点**: 优化了 URL 正则表达式 `r'(https?://|www\.)[^\s()<>]+(?<![.,;?!])'` 以正确处理句末标点。
*   **状态**: 单元测试覆盖率 100%，已集成。
*   **相关文件**: [backend/core/link_filter.py](backend/core/link_filter.py), [backend/core/ingest.py](backend/core/ingest.py)

### 1.3 搜索接口语义缓存 (`Search Caching`)
*   **需求**: 为 `/api/search` 接口添加类似 Chat 的语义缓存功能，但需隔离作用域。
*   **实现**:
    *   重构 `backend/core/cache.py`：`lookup` 和 `update` 方法增加 `scope` 参数。
    *   **ID 生成策略变更**: 使用 `hash(query + scope)` 生成 ID，确保 ChromaDB 中不同 scope 的相同 query 不会 ID 冲突。
    *   在 `backend/app.py` 的 `/api/search` 逻辑中加入缓存读写操作。
*   **状态**: 已验证缓存命中和数据一致性。
*   **相关文件**: [backend/core/cache.py](backend/core/cache.py), [backend/app.py](backend/app.py)

## 2. 遇到的问题与解决方案 (Issues & Solutions)

### 2.1 模块导入错误 (`ModuleNotFoundError`)
*   **问题**: 运行 `backend/tests/test_retriever.py` 时报错 `No module named 'core'`。
*   **原因**: 测试脚本直接运行时，`sys.path` 未包含项目根目录（backend）。
*   **解决**: 在测试脚本头部添加路径修正代码：
    ```python
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    ```

### 2.2 代码语法与定义错误 (`SyntaxError` / `NameError`)
*   **问题 1**: `app.py` 中缺少 `List`, `Dict`, `Any` 的导入，导致 `SummarizeRequest` 定义失败。
*   **解决**: 添加 `from typing import List, Dict, Any`。
*   **问题 2**: 在编辑 `app.py` 时意外在全局作用域遗留了字符 `c`，导致服务启动失败。
*   **解决**: 删除该字符，恢复代码结构。

### 2.3 端口占用问题
*   **问题**: 测试过程中发现 `8000` 端口被之前的进程占用。
*   **解决**: 使用 `netstat` 定位进程 ID，并使用 `taskkill /F /PID <pid>` 强制释放端口。

### 2.4 正则表达式边界情况
*   **问题**: 初始的 URL 过滤正则会错误地吞掉 URL 后的标点符号（如句号），导致文本粘连或语义不通。
*   **解决**: 引入 Negative Lookbehind `(?<!...)` 确保不匹配 URL 结尾的标点符号。

## 3. 测试验证 (Verification)

本次开发包含了完整的测试流程：
1.  **test_summarize_api.py**: 验证摘要接口的流式输出和空数据处理。
2.  **test_link_filter.py**: 验证多种格式链接的过滤效果及元数据保护。
3.  **test_search_cache.py**: 验证搜索接口在第二次请求时正确命中缓存，且结果一致。

所有测试脚本均已通过。

---

## 4. 本轮新增改进总结（2026-01-15）

### 4.1 检索与排序改进
*   **问题**：
    *   仅依赖向量相似度时，部分长尾关键词召回的结果相关性不稳定。
    *   `/api/search` 接口无法直接在前端看到总耗时信息。
*   **改进**：
    *   在 `retriever.py` 中集成 BM25 关键词检索，并与向量分数按权重融合：
        *   新增 `BM25Scorer`，实现标准 BM25 公式，支持文档长度校正。
        *   在候选集上计算 BM25 分数，与向量/重排分数一起进行 Min-Max 归一化。
        *   使用可配置权重（默认：关键词 0.4，向量 0.6）加权求和，得到 `hybrid_score` 并重新排序。
        *   通过简单的 token 缓存（按文档 ID 缓存分词结果）降低重复分词开销。
    *   在 `config.py` 中增加 BM25 相关开关：
        *   `BM25_ENABLED`: 是否启用 BM25 融合。
        *   `BM25_KEYWORD_WEIGHT`、`BM25_VECTOR_WEIGHT`: 权重参数，内部归一化并做防御性校验。
    *   在 `/api/search` 接口中返回更多调试信息：
        *   增加 `latency_ms` 字段，表示本次请求的端到端耗时。
        *   增加 `from_cache` 字段，标记是否命中 Redis + Chroma 的语义缓存。
        *   保持原有 `results` 列表结构不变（包含 `score` 和 `rerank_score`）。

### 4.2 生成模型与置信度控制
*   **问题**：
    *   生成模型和改写模型的来源不一致，不便统一切换本地/云端模型。
    *   即使检索结果质量较差，生成端仍会尝试“硬编”回答。
*   **改进**：
    *   在 `config.py` 中引入生成模型提供方开关：
        *   `GENERATE_PROVIDER`：
            *   `"qwen"`：默认，生成与改写共用本地 Qwen（通过 `LLM_BASE_URL` / REWRITE_*）。
            *   `"gemini"`：使用 OpenAI 兼容网关调用 Gemini 模型。
        *   `GEMINI_MODEL_NAME`：单独配置 Gemini 模型名称。
    *   在 `generator.py` 的构造函数中根据 `GENERATE_PROVIDER` 动态选择：
        *   Qwen 模式下共用改写模型与 Ollama base_url。
        *   Gemini 模式下使用 OpenAI 兼容的 base_url 与 API key。
    *   为生成增加“最低置信度”控制逻辑：
        *   如果传入的 `docs` 为空，继续返回“未找到相关通知”。
        *   新增阈值规则：若所有文档的 `score < 0.5` 或 `rerank_score <= 0`，同样视为未找到通知，拒绝生成。
        *   记录 `generate_low_confidence` 日志事件，便于后续统计该类拒答比例。

### 4.3 前端体验与调试信息提升
*   **问题**：
    *   Streamlit 前端配色偏“红色校园主题”，与“极简高级”的目标不完全契合。
    *   `/api/search` 的缓存命中与耗时信息前端不可见。
*   **改进**：
    *   全面重构 `streamlit_app.py` 的 CSS 注入：
        *   引入类似“瑞士温泉”风格的浅灰+青绿色极简配色（背景、卡片、按钮、边框统一由 CSS 变量管理）。
        *   简化 stepper 的颜色与高亮效果，使用 SVG 图标替代字符符号。
        *   优化按钮、输入框、侧边栏间距，使布局在桌面与移动端都保持紧凑但不拥挤。
    *   文档卡片新增评分展示：
        *   除原有 `score` 外，增加 `rerank` 分数展示，用于观察 BM25+向量融合前后的效果。
    *   请求耗时可视化：
        *   在实时检索区域顶部显示 `检索耗时：xxx ms`，并在命中缓存时附加“（缓存命中）”提示。
    *   示例问题轮播：
        *   在页面标题旁通过前端 JS 轮播 10 个预设问题，方便新用户快速理解可问的问题类型。

### 4.4 数据预处理与分块策略
*   **问题**：
    *   原始 Markdown 文档中的链接在正文与元数据中混杂，不利于模型输入。
    *   一些章节内容过短，导致向量检索粒度过细，语义不稳定。
*   **改进**：
    *   链接过滤模块：
        *   在 `link_filter.py` 中实现 HTML/Markdown/纯文本 URL 的严格过滤逻辑，确保正文中不残留任何 URL。
        *   `filter_metadata` 保证元数据结构和链接完全保留，方便前端展示和用户跳转。
    *   分块逻辑增强（`ingest.py`）：
        *   为 `DocumentProcessor` 引入 `min_chunk_size` 概念，通过 `_merge_small_splits` 合并过小的 Header 段，使得每个 chunk 至少达到一定长度。
        *   调整默认 `chunk_size` 参数，为大规模检索场景提供更稳健的粒度控制。
