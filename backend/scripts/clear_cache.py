import os
import sys
from pathlib import Path


def main():
    here = Path(__file__).resolve()
    backend_dir = here.parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.append(str(backend_dir))

    from core.cache import semantic_cache

    print("Clearing semantic cache (Redis + Chroma)...")
    semantic_cache.clear_all()
    print("Done.")


if __name__ == "__main__":
    main()

