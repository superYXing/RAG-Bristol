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
