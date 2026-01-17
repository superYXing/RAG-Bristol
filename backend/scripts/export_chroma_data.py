import sys
import os
import json
import logging
from pathlib import Path

# Add backend to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))

try:
    from backend.core.vector_store import vector_store
except ImportError:
    sys.path.append(str(Path.cwd()))
    from backend.core.vector_store import vector_store

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def export_data():
    # Define output directory
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)
    
    if not vector_store.collection:
        logger.error("Vector store collection not found. Make sure ChromaDB is initialized.")
        return

    try:
        # 获取所有集合
        collections = vector_store.client.list_collections()
        logger.info(f"Found {len(collections)} collections: {[c.name for c in collections]}")
    except Exception as e:
        logger.error(f"Could not list collections: {e}")
        return

    for col in collections:
        export_collection(col, output_dir)

def export_collection(collection, output_dir):
    name = collection.name
    count = collection.count()
    logger.info(f"Total documents in {name}: {count}")
    
    if count == 0:
        logger.warning(f"Collection {name} is empty. Skipping.")
        return

    logger.info(f"Retrieving data for {name}...")
    try:
        # 修改点 1: 在 get 方法的 include 参数中移除 "embeddings"
        # 这样数据库就不会返回向量数据，速度更快且不占内存
        results = collection.get(
            include=["documents", "metadatas"] 
        )
    except Exception as e:
        logger.error(f"Failed to fetch data for {name}: {e}")
        return
    
    ids = results['ids']
    documents = results['documents']
    metadatas = results['metadatas']
    
    export_data = []
    limit = min(500, len(ids))
    logger.info(f"Exporting first {limit} records from {name}...")
    
    for i in range(limit):
        item = {
            "id": ids[i],
            "document": documents[i],
            "metadata": metadatas[i]
        }
            
        export_data.append(item)
        
    output_file = output_dir / f"chroma_export_{name}_first{limit}.json"
    
    logger.info(f"Writing {len(export_data)} records to {output_file}...")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Successfully exported {name} to {output_file}")
    except Exception as e:
        logger.error(f"Failed to write output file: {e}")

if __name__ == "__main__":
    export_data()
