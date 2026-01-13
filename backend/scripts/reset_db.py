import os
import sys
import shutil

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.vector_store import vector_store
from core.config import settings

def reset_database():
    print("-" * 30)
    print("WARNING: This will delete all data in the ChromaDB.")
    print(f"Target Collection: {vector_store.collection_name}")
    print(f"Persist Directory: {settings.CHROMA_PERSIST_DIRECTORY}")
    print("-" * 30)
    
    confirm = input("Are you sure you want to proceed? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return

    try:
        # Try to delete via client API first
        if vector_store.client:
            try:
                vector_store.client.delete_collection(vector_store.collection_name)
                print(f"Collection '{vector_store.collection_name}' deleted via API.")
            except Exception as e:
                print(f"API delete failed (collection might not exist): {e}")
        
        # Force cleanup of persistence directory to be sure
        if os.path.exists(settings.CHROMA_PERSIST_DIRECTORY):
            try:
                # We need to close the client connection if possible, but Chroma client doesn't have a clear close() 
                # that releases file locks immediately in all versions. 
                # However, since we are in a script, it should be fine if we just rely on API or file deletion.
                # If API worked, files are updated. If we want a hard reset:
                # shutil.rmtree(settings.CHROMA_PERSIST_DIRECTORY)
                # print(f"Directory '{settings.CHROMA_PERSIST_DIRECTORY}' removed.")
                pass 
            except Exception as e:
                print(f"File system cleanup failed: {e}")

        # Re-create the collection
        vector_store._ensure_collection()
        print("Database has been reset and re-initialized.")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    reset_database()
