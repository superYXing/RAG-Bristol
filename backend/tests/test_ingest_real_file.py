import sys
import os

# 添加 backend 目录到 path 以便导入 core 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.ingest import DocumentProcessor

def test_real_file_ingest():
    # 定义目标文件路径
    # 注意：根据用户当前工作目录结构
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    target_file = os.path.join(base_dir, r"bristol_markdown\students\life-in-bristol\campus\cafes\cafes.md")
    
    print(f"Testing file: {target_file}")
    
    if not os.path.exists(target_file):
        print(f"Error: File not found at {target_file}")
        return

    processor = DocumentProcessor(chunk_size=1000, chunk_overlap=200)
    chunks = processor.process_file(target_file)
    
    output_file = os.path.join(os.getcwd(), "output.txt")
    print(f"\nTotal Chunks Generated: {len(chunks)}")
    print(f"Writing output to: {output_file}")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Source File: {target_file}\n")
        f.write(f"Total Chunks: {len(chunks)}\n\n")
        
        for i, chunk in enumerate(chunks):
            header = f"{'='*20} Chunk {i+1} {'='*20}\n"
            print(header.strip()) # 仍然打印到控制台以供快速查看
            f.write(header)
            
            f.write("Metadata:\n")
            for k, v in chunk.metadata.items():
                line = f"  {k}: {v}\n"
                print(line.strip())
                f.write(line)
            
            f.write("\nContent:\n")
            f.write(chunk.page_content)
            f.write("\n")
            f.write("-" * 50 + "\n\n")
            
            # 简单打印内容预览到控制台
            print("\nContent Preview:")
            print(chunk.page_content[:100] + "..." if len(chunk.page_content) > 100 else chunk.page_content)
            print("-" * 50)
            
    print(f"\nSuccessfully wrote all chunks to {output_file}")

if __name__ == "__main__":
    test_real_file_ingest()
