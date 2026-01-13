import frontmatter
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from typing import List, Dict, Any
import os
from datetime import datetime

class DocumentProcessor:
    def __init__(self, chunk_size=1000, chunk_overlap=200):
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

    def process_file(self, file_path: str) -> List[Dict[str, Any]]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
            
            base_metadata = post.metadata
            content = post.content
            
            # --- 优化元信息 ---
            
            # 1. 基础字段补全
            if 'title' not in base_metadata:
                # 尝试使用 h1 或文件名
                base_metadata['title'] = os.path.basename(file_path).replace('.md', '').replace('-', ' ').title()
            if 'url' not in base_metadata:
                base_metadata['url'] = ""
            if 'date' not in base_metadata:
                base_metadata['date'] = str(datetime.now().date())
            else:
                base_metadata['date'] = str(base_metadata['date'])
            
            # 2. 从文件路径提取分类信息 (Category extraction from path)
            # 用户要求不需要 category, subcategory, topic 这三个字段
            # 假设路径结构: .../bristol_markdown/{category}/{subcategory}/{topic}/{file}.md
            # 我们寻找 'bristol_markdown' 之后的路径部分
            # path_parts = os.path.normpath(file_path).split(os.sep)
            # try:
            #     if 'bristol_markdown' in path_parts:
            #         idx = path_parts.index('bristol_markdown')
            #         # 获取 bristol_markdown 后的部分
            #         rel_parts = path_parts[idx+1:-1] # -1 去掉文件名
                    
            #         if len(rel_parts) >= 1:
            #             base_metadata['category'] = rel_parts[0]
            #         if len(rel_parts) >= 2:
            #             base_metadata['subcategory'] = rel_parts[1]
            #         if len(rel_parts) >= 3:
            #             base_metadata['topic'] = rel_parts[2]
            # except Exception as e:
            #     print(f"路径解析警告: {e}")

            # --- 分块策略 ---

            # 1. Markdown 标题切分
            header_splits = self.markdown_splitter.split_text(content)
            
            # 2. 递归字符切分 & 合并元数据
            final_chunks = []
            
            for split in header_splits:
                # 合并 Frontmatter 元数据和 Header 元数据 (h1, h2, h3)
                combined_metadata = base_metadata.copy()
                combined_metadata.update(split.metadata)
                
                # 对每个 header block 进行二次切分
                chunks = self.text_splitter.create_documents([split.page_content], metadatas=[combined_metadata])
                final_chunks.extend(chunks)
                
            return final_chunks
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
            return []

processor = DocumentProcessor()
