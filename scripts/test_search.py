from duckduckgo_search import DDGS
import json

try:
    print("Testing DuckDuckGo Search...")
    with DDGS() as ddgs:
        results = list(ddgs.text("current CEO of OpenAI", max_results=1))
        print(json.dumps(results, indent=2))
except Exception as e:
    print(f"Error: {e}")
