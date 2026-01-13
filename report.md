# 项目优化报告 (Project Optimization Report)

## 1. 历史对话优化记录 (Optimization History)

### 1.1 前端现代化与 UI/UX 升级
*   **Tailwind CSS 迁移**: 引入了 `@theme` 配置，建立了基于 CSS 变量的设计系统，支持动态主题切换（深色/浅色模式）。
*   **主题定制**: 将品牌主色调从默认蓝色调整为红色（Bristol Red），并应用了全新的配色方案。
*   **响应式布局**: 实现了可折叠的侧边栏历史记录，确保在移动端和桌面端的良好体验。
*   **Logo 集成**: 在头部导航栏集成了学校 Logo，提升品牌识别度。

### 1.2 核心功能增强
*   **历史记录持久化**: 使用 `localStorage` 实现了用户会话的本地存储，即使刷新页面也能保留对话上下文。
*   **会话分组**: 实现了按时间维度（今天、昨天、更早）自动分组显示历史会话。
*   **来源详情模态框 (Source Modal)**:
    *   设计了包含元数据、完整内容预览的模态框。
    *   实现了点击引用标记 `[1]` 直接唤起模态框的交互。
    *   集成了 **Web Share API** 和 **Clipboard API**，支持内容的一键复制和分享。
    *   添加了键盘 `Esc` 关闭和背景点击关闭等无障碍交互支持。
*   **引用展示优化**:
    *   在右侧参考资料面板中显示文档的相关性分数（Score）。
    *   添加了 "Read Full" 按钮，允许用户查看被截断的长文本完整内容。

### 1.3 性能与工程化
*   **流式响应优化**: 改进了前端对后端 SSE 流的处理逻辑，实现了平滑的打字机效果。
*   **构建修复**: 解决了 TypeScript 类型定义缺失（如 `StepStatus`）和图标库 `lucide-react` 导入不完整导致的构建失败问题。

## 2. 问题解决方案 (Problem Solutions)

### 2.1 引用来源无法查看完整内容
*   **问题**: 用户反馈右侧参考资料面板中的文本被截断，且无法查看全文。
*   **解决方案**:
    1.  在 `SourceDoc` 接口中扩展了 `score` 和 `date` 字段。
    2.  后端 `generator.py` 更新，在返回的 `__SOURCES__` JSON 数据中包含 `rerank_score`。
    3.  前端 `App.tsx` 新增 "Read Full" 按钮，点击后复用 `SourceModal` 展示完整文档内容。

### 2.2 页面白屏与构建错误
*   **问题**: 在引入新图标和组件后，构建失败或运行时可能出现白屏。
*   **解决方案**:
    1.  检查并补全了 `lucide-react` 的所有图标导入。
    2.  修复了 TypeScript 接口定义，确保所有状态变量都有明确类型。
    3.  验证了 `useEffect` 中的事件监听器逻辑，防止内存泄漏。

### 2.3 历史记录丢失
*   **问题**: 刷新页面后对话清空。
*   **解决方案**: 引入 `localStorage` 中间件逻辑，在 `App.tsx` 中监听 `sessions` 状态变化并自动同步到本地存储。

### 2.4 主题一致性
*   **问题**: 品牌色需要统一修改。
*   **解决方案**: 在 `index.css` 中集中管理 CSS 变量，将 `--color-brand-*` 系列变量整体替换为红色系色值，实现了全局一键换肤。

---
*报告生成时间: 2026-01-13*

**已完成的历史改动总结（按问题→修复）**

- **Milvus 在 Windows 不可用/连接报错**
  - 从 Milvus 切换为 **ChromaDB** 持久化存储，并增加容错（失败走 Mock）。
  - 相关： [vector_store.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/vector_store.py)

- **向量分数出现负数、分数含义不清**
  - 明确 Chroma 距离度量，改为 **cosine**，并统一 `score = 1 - distance` 的语义解释与调试输出。
  - 相关： [vector_store.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/vector_store.py)、[test_chroma_connection.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/tests/test_chroma_connection.py)

- **embedding/rerank 使用本地模型导致部署复杂**
  - Embedding 改为云端 `text-embedding-3-small`；Rerank 改为云端 `BAAI/bge-reranker-v2-m3`（与 `OPENAI_BASE_URL` 同源）。
  - 相关： [config.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/config.py)、[retriever.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/retriever.py)、[vector_store.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/vector_store.py)

- **日期检索逻辑不需要**
  - 删除 date_start/date_end 相关参数与前端过滤逻辑。
  - 相关： [app.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/app.py)、[App.tsx](file:///c%3A/Users/37011/Desktop/RAG-Bristol/frontend/src/App.tsx)

- **检索前需要翻译/关键词提炼、检索后需要客服式总结+引用链接**
  - 增加 query rewrite（翻译+关键词）与生成 Prompt，要求引用 `[编号]` 并给出官网链接。
  - 相关： [retriever.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/retriever.py)、[generator.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/generator.py)

- **前端需要显示“前三个分片”并支持悬浮展示全文**
  - 后端流式首段输出 `__SOURCES__:{json}\n`；前端解析该前缀并渲染 hover 预览组件。
  - 相关： [generator.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/generator.py)、[App.tsx](file:///c%3A/Users/37011/Desktop/RAG-Bristol/frontend/src/App.tsx)

- **离线索引与 ChromaDB 无文件/任务不执行**
  - 增加离线索引脚本，明确 Celery worker 执行；修复路径问题；并把索引流程改为上线前一次性入库（默认 async）。
  - 相关： [offline_index.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/scripts/offline_index.py)、[tasks.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/tasks.py)

- **批量入库报错：`Document object is not subscriptable`**
  - `add_documents` 兼容 LangChain `Document` 与 dict 两种输入。
  - 相关： [vector_store.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/vector_store.py)

- **批量入库报错：重复 ID / upsert 字段长度不一致**
  - 改用 `upsert`；并在生成 embeddings 前先做 batch 内去重，保证 ids/documents/metadatas/embeddings 长度一致。
  - 相关： [vector_store.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/vector_store.py)

- **引入 Redis 语义缓存（语义相似直接复用上次答案）**
  - 新增 `SemanticCache`：Redis 存答案、Chroma 存 query 向量索引；命中缓存按流式协议返回（含 `__SOURCES__`）。
  - 相关： [cache.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/cache.py)、[app.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/app.py)

- **上线后不需要每次问答都 ingest；清理无用 API**
  - 删除 `/api/ingest` 上传入库接口；只保留 `/api/search` 与 `/api/chat`。
  - 相关： [app.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/app.py)

- **generator 的 full_response 累加低效**
  - 改为 list 累积后 join，并缓存 sources+正文，保证缓存命中时前端仍能展示 sources。
  - 相关： [generator.py](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/core/generator.py)

- **前端构建失败：Tailwind v4 PostCSS 插件变更**
  - `postcss.config.js` 改用 `@tailwindcss/postcss` 并安装依赖，`npm run build` 通过。
  - 相关： [postcss.config.js](file:///c%3A/Users/37011/Desktop/RAG-Bristol/frontend/postcss.config.js)

- **前端 lint/tsc 报错（any、类型不一致）**
  - 补齐 `SourceDoc/SearchHit` 类型、定时器类型，去掉显式 any，lint 与 tsc 通过。
  - 相关： [App.tsx](file:///c%3A/Users/37011/Desktop/RAG-Bristol/frontend/src/App.tsx)

- **测试与调试脚本补全**
  - 增加/完善 Chroma 连接测试、端到端对话测试、真实文件 ingest 测试等。
  - 相关： [backend/tests](file:///c%3A/Users/37011/Desktop/RAG-Bristol/backend/tests)

如果你想要“按时间线”的提交级别 changelog（每次需求迭代对应哪些文件改动），我也可以再整理成一份更细的列表。