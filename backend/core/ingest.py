import frontmatter
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from typing import List, Dict, Any
import os
from datetime import datetime
from core.link_filter import LinkFilter # 假设你之前添加了这个引用

class DocumentProcessor:
    def __init__(self, chunk_size=3000, chunk_overlap=550, min_chunk_size=1500):
        """
        :param chunk_size: 目标切片最大长度
        :param chunk_overlap: 切片重叠长度
        :param min_chunk_size: 最小切片长度（新增参数），小于此长度的段落将被合并
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size  # 新增：最小字符数限制
        
        self.link_filter = LinkFilter()

        # 1. 首先按 Markdown 标题切分
        self.headers_to_split_on = [
            ("#", "h1"),
            ("##", "h2"),
            ("###", "h3"),
        ]
        self.markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=self.headers_to_split_on)

        # 2. 然后按字符切分长段落
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def _merge_small_splits(self, splits):
        """
        核心逻辑：遍历 header_splits，如果当前块太小，就吸附下一个块，直到满足最小长度。
        """
        if not splits:
            return []
            
        merged_splits = []
        current_split = splits[0]
        
        for i in range(1, len(splits)):
            next_split = splits[i]
            
            # 如果当前切片长度小于最小限制，则进行合并
            if len(current_split.page_content) < self.min_chunk_size:
                # 1. 合并内容：中间加换行符
                current_split.page_content += "\n\n" + next_split.page_content
                
                # 2. 合并元数据（可选）：
                # MarkdownHeaderTextSplitter 会把标题放入 metadata。
                # 当我们合并 Section A 和 Section B 时，通常保留 Section A 的元数据（作为起始点）。
               
            else:
                # 如果当前块已经足够大，先保存它，然后开启新的块
                merged_splits.append(current_split)
                current_split = next_split
        
        # 处理循环结束后的最后一个块
        if current_split:
            # 如果最后一个块依然很小，且前面有已合并的块，尝试合并到前一个块（避免尾部产生极小碎片）
            if len(current_split.page_content) < self.min_chunk_size and merged_splits:
                merged_splits[-1].page_content += "\n\n" + current_split.page_content
            else:
                merged_splits.append(current_split)
                
        return merged_splits

    def process_file(self, file_path: str) -> List[Dict[str, Any]]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
            
            base_metadata = post.metadata
            content = post.content
            
            # --- 链接过滤 ---
            if hasattr(self, 'link_filter'):
                 content = self.link_filter.filter_content(content)
                 base_metadata = self.link_filter.filter_metadata(base_metadata)
            
            # --- 优化元信息 ---
            if 'title' not in base_metadata:
                base_metadata['title'] = os.path.basename(file_path).replace('.md', '').replace('-', ' ').title()
            if 'url' not in base_metadata:
                base_metadata['url'] = ""
            if 'date' not in base_metadata:
                base_metadata['date'] = str(datetime.now().date())
            else:
                base_metadata['date'] = str(base_metadata['date'])

            # --- 分块策略 ---

            # 1. 第一步：Markdown 标题粗切
            header_splits = self.markdown_splitter.split_text(content)
            
            # 【新增步骤】：合并过小的标题块
            # 如果标题下内容极少，这一步会将其合并到一起
            merged_header_splits = self._merge_small_splits(header_splits)
            
            # 2. 第二步：递归字符切分 & 合并元数据
            final_chunks = []
            
            for split in merged_header_splits:
                # 合并 Frontmatter 元数据和 Header 元数据
                combined_metadata = base_metadata.copy()
                combined_metadata.update(split.metadata)
                
                # 对每个 (可能已经合并过的) header block 进行二次切分
                # 注意：如果合并后的块超过了 chunk_size，这里会再次把它切开，所以不用担心合并导致块过大
                chunks = self.text_splitter.create_documents([split.page_content], metadatas=[combined_metadata])
                final_chunks.extend(chunks)
                
            return final_chunks
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
            return []


processor = DocumentProcessor()
