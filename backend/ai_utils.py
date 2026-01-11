import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

XAI_API_KEY = os.getenv("XAI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

CACHE_FILE = "api_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)

def get_from_cache(key):
    cache = load_cache()
    if key in cache:
        item = cache[key]
        # Cache for 7 days
        expire_time = datetime.fromisoformat(item['timestamp']) + timedelta(days=7)
        if datetime.now() < expire_time:
            return item['value']
    return None

def add_to_cache(key, value):
    cache = load_cache()
    cache[key] = {
        'value': value,
        'timestamp': datetime.now().isoformat()
    }
    save_cache(cache)

def call_serper(query):
    cache_key = f"serper_{query}"
    cached = get_from_cache(cache_key)
    if cached:
        return cached

    if not SERPER_API_KEY:
        return "Serper API key not found"

    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query})
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        data = response.json()
        
        # Extract snippets
        snippets = []
        if 'organic' in data:
            for item in data['organic'][:3]:
                snippets.append(item.get('snippet', ''))
        
        result = " ".join(snippets)
        add_to_cache(cache_key, result)
        return result
    except Exception as e:
        print(f"Serper error: {e}")
        return str(e)

def call_grok(prompt, system_prompt="Sen bir IT altyapı risk analiz uzmanısın."):
    cache_key = f"grok_{prompt[:100]}_{system_prompt[:50]}"
    cached = get_from_cache(cache_key)
    if cached:
        return cached

    if not XAI_API_KEY:
        return "xAI API key not found"

    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {XAI_API_KEY}"
    }
    data = {
        "model": "grok-4-1-fast-reasoning", # Fallback to grok-beta if grok-4-1-fast-reasoning is not exactly correct in API
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }
    
    # Try using the requested model name if it's confirmed
    # Since search said it is a "new model", I'll try to use it if it works
    # However, user mentioned 'grok-4-1-fast-reasoning'. I'll try it first.
    data["model"] = "grok-4-1-fast-reasoning"

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            # Fallback to grok-beta if the specific model is not found
            data["model"] = "grok-beta"
            response = requests.post(url, headers=headers, json=data)
        
        response.raise_for_status()
        result_data = response.json()
        content = result_data['choices'][0]['message']['content']
        add_to_cache(cache_key, content)
        return content
    except Exception as e:
        print(f"Grok error: {e}")
        return str(e)
