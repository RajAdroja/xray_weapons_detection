"""
Simple cache for storing large result data temporarily
"""
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

class ResultCache:
    """Simple file-based cache for storing large result data"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def store(self, key: str, data: Dict[str, Any]) -> str:
        """Store data and return cache key"""
        cache_file = self.cache_dir / f"{key}.json"
        
        # Add timestamp for cleanup
        cache_data = {
            "data": data,
            "timestamp": time.time()
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
        
        return str(cache_file)
    
    def retrieve(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from cache"""
        cache_file = self.cache_dir / f"{key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            return cache_data.get("data")
        except:
            return None
    
    def cleanup_old(self, max_age_seconds: int = 3600):
        """Clean up old cache files"""
        current_time = time.time()
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                if current_time - cache_data.get("timestamp", 0) > max_age_seconds:
                    cache_file.unlink()
            except:
                # Remove corrupted files
                cache_file.unlink()

# Global cache instance
result_cache = ResultCache()