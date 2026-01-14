import os
import sys
import argparse
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.tasks import process_and_index_doc

def offline_index(directory: str, extensions: list = ['.md'], mode: str = 'sync'):
    """
    遍历目录，处理文件。
    mode: 'sync' (同步直接处理) | 'async' (通过 Celery 分发)
    """
    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return

    print(f"Scanning {directory} for {extensions} files...")
    
    files_to_process = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                files_to_process.append(os.path.join(root, file))
    
    total_files = len(files_to_process)
    print(f"Found {total_files} files.")
    
    if total_files == 0:
        return

    print(f"Starting indexing in [{mode.upper()}] mode...")
    
    success_count = 0
    error_count = 0

    if mode == 'async':
        print("Dispatching Celery tasks...")
        for file_path in tqdm(files_to_process):
            try:
                process_and_index_doc.delay(file_path)
                success_count += 1
            except Exception as e:
                print(f"Failed to dispatch task for {file_path}: {e}")
                error_count += 1
        
        print(f"\nDispatched {success_count} tasks.")
        print("IMPORTANT: You MUST start the Celery worker to process these tasks:")
        print("  celery -A core.tasks worker --loglevel=info -P solo")
        
    else:
        print("Processing files directly (this may take a while)...")
        from core.ingest import processor
        from core.vector_store import vector_store
        
        all_chunks_buffer = []
        BUFFER_SIZE = 200
        
        for file_path in tqdm(files_to_process):
            try:
                chunks = processor.process_file(file_path)
                if chunks:
                    all_chunks_buffer.extend(chunks)
                    
                    if len(all_chunks_buffer) >= BUFFER_SIZE:
                        vector_store.add_documents(all_chunks_buffer)
                        all_chunks_buffer = []
                        
                    success_count += 1
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                error_count += 1
        
        if all_chunks_buffer:
            vector_store.add_documents(all_chunks_buffer)
        
        print(f"\nCompleted. Processed {success_count} files (Errors: {error_count}).")
        print(f"ChromaDB should now be populated in: {vector_store.collection_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline Indexing Script")
    parser.add_argument("--dir", type=str, default="../bristol_markdown", help="Directory containing Markdown files")
    parser.add_argument("--mode", type=str, default="sync", choices=["sync", "async"], 
                        help="Execution mode: 'sync' (direct) or 'async' (via Celery, default)")
    args = parser.parse_args()
    
    target_dir = args.dir
    if not os.path.isabs(target_dir):
        target_dir = os.path.abspath(target_dir)
        
    offline_index(target_dir, mode=args.mode)
