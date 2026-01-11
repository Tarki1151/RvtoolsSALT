import os
import json
import hashlib
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

XAI_API_KEY = os.getenv("XAI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

CACHE_FILE = "api_cache.json"
REMEDIATION_CACHE_FILE = "remediation_cache.json"

def load_remediation_cache():
    if os.path.exists(REMEDIATION_CACHE_FILE):
        try:
            with open(REMEDIATION_CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_remediation_cache(cache):
    with open(REMEDIATION_CACHE_FILE, 'w') as f:
        json.dump(cache, f)

def normalize_message(message):
    """
    Normalize message by removing host names, IPs, VM names, dates etc.
    This ensures similar errors share the same cache entry.
    """
    import re
    
    normalized = message
    
    # Replace hostnames (xxx.domain.local, xxx.ocloud.local, etc.)
    normalized = re.sub(r'\b[a-zA-Z0-9_-]+\.(ocloud|local|vmware|vsphere|domain)\.[a-zA-Z]+\b', '[HOSTNAME]', normalized)
    
    # Replace IP addresses
    normalized = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]', normalized)
    
    # Replace dates (various formats)
    normalized = re.sub(r'\b\d{2,4}[/\-\.]\d{2}[/\-\.]\d{2,4}\b', '[DATE]', normalized)
    normalized = re.sub(r'\b\d{2}:\d{2}:\d{2}\b', '[TIME]', normalized)
    
    # Replace VM-like names (common patterns like VM_xxx, srv-xxx, etc.)
    normalized = re.sub(r'\b(VM_|SRV|CIM_|DC-)[A-Za-z0-9_-]+\b', '[VM]', normalized, flags=re.IGNORECASE)
    
    # Replace cluster names in format "cluster X in Y DC"
    normalized = re.sub(r'cluster\s+[A-Za-z0-9_\s-]+\s+in\s+[A-Za-z0-9_\s-]+\s+DC', 'cluster [CLUSTER] in [DC]', normalized, flags=re.IGNORECASE)
    
    # Replace datastore names
    normalized = re.sub(r'\b[A-Za-z0-9_-]+_datastore[A-Za-z0-9_-]*\b', '[DATASTORE]', normalized, flags=re.IGNORECASE)
    
    # Replace snapshot restore point timestamps
    normalized = re.sub(r'Restore Point\s+[\d\.\s:]+created on\s+[\d\./\s:]+', 'Restore Point [TIMESTAMP]', normalized)
    
    return normalized.strip()

def get_remediation_advice(message):
    if not message:
        return None
        
    # Normalize message for cache lookup
    normalized_message = normalize_message(message)
    
    cache = load_remediation_cache()
    if normalized_message in cache:
        print(f"Cache hit for: {normalized_message[:50]}...")
        return cache[normalized_message]

    print(f"Generating remediation advice for: {normalized_message[:80]}...")
    
    # 1. Search for the error
    search_results = call_serper(f"VMware ESXi health check error remediation: {message}")
    
    # 2. Ask Grok for actionable steps
    prompt = f"""
Aşağıdaki VMware ESXi sağlık kontrolü uyarısı için:
1. Önce bu sorunun nelere yol açabileceğini tek bir kısa cümle ile açıkla (⚠️ Etki: şeklinde başla)
2. Sonra kısa, öz ve uygulanabilir çözüm adımları (remediation steps) listele

Sadece teknik bilgi ver. Türkçe cevap ver.

Uyarı: {message}

Araştırma Verisi:
{search_results}

Format:
⚠️ Etki: [Sorunun potansiyel etkisi - tek cümle]

Çözüm Adımları:
- Adım 1
- Adım 2
...
"""
    advice = call_grok(prompt, system_prompt="Sen deneyimli bir VMware Sanallaştırma ve Altyapı Uzmanısın.")
    
    if advice and "error" not in advice.lower():
        cache[normalized_message] = advice
        save_remediation_cache(cache)
        return advice
        
    return None

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
    # Use hash to ensure unique cache keys
    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    cache_key = f"serper_{query_hash}"
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
    # Use hash to ensure unique cache keys for different prompts
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    cache_key = f"grok_{prompt_hash}"
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
