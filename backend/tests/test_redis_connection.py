import os
import sys
import redis
from dotenv import load_dotenv

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_redis_connection():
    load_dotenv()
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"Testing Redis connection to: {redis_url}")
    
    try:
        r = redis.from_url(redis_url)
        response = r.ping()
        if response:
            print("Successfully connected to Redis! PING -> PONG")
            return True
        else:
            print("Connected but no PONG response.")
            return False
    except redis.exceptions.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        print("\nTroubleshooting tips:")
        print("1. If Redis is running in WSL, ensure it's listening on localhost.")
        print("   Edit /etc/redis/redis.conf in WSL and change 'bind 127.0.0.1 ::1' to 'bind 0.0.0.0' or ensure 'bind 127.0.0.1' is set.")
        print("   Restart Redis in WSL: sudo service redis-server restart")
        print("2. Ensure Redis server is running.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    test_redis_connection()
