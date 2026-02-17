from tavily import TavilyClient
from duckduckgo_search import DDGS
import os

API_KEY = "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"
QUERY = "who won super bowl 2026"

print(f"--- Reproducing Search Failure for '{QUERY}' ---\n")

# 1. Test Tavily
try:
    print("1. Testing Tavily...")
    tavily = TavilyClient(api_key=API_KEY)
    response = tavily.search(query=QUERY, search_depth="basic", max_results=3)
    print(f"RAW TAVILY RESPONSE: {response}")
    results = response.get("results", [])
    if results:
        print(f"✅ Tavily Found: {results[0]['title']}")
    else:
        print("❌ Tavily returned empty results.")
except Exception as e:
    print(f"❌ Tavily Error: {e}")

# 2. Test DuckDuckGo
print("\n2. Testing DuckDuckGo...")
try:
    with DDGS() as ddgs:
        results = list(ddgs.text(QUERY, max_results=3))
        if results:
            print(f"✅ DDG Found: {results[0]['title']}")
            print(f"   Body: {results[0]['body'][:100]}...")
        else:
            print("❌ DDG returned empty results.")
except Exception as e:
    print(f"❌ DDG Error: {e}")
