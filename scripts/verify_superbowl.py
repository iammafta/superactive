from tavily import TavilyClient
import os

# Load key from env or hardcode for test
API_KEY = "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"

print(f"--- Verifying Super Bowl 2026 Result ---")
try:
    tavily = TavilyClient(api_key=API_KEY)
    # Search specifically for the winner to see what comes up
    query = "who won super bowl 2026 winner"
    response = tavily.search(query=query, search_depth="basic", max_results=3)
    
    print(f"Query: {query}")
    found_seahawks = False
    for r in response.get("results", []):
        print(f"\nTitle: {r['title']}")
        print(f"Content: {r['content']}")
        if "Seahawks" in r['title'] or "Seahawks" in r['content']:
            found_seahawks = True
    
    if found_seahawks:
        print("\n✅ Verified: Found 'Seahawks' in results.")
    else:
        print("\n⚠️ Warning: Did NOT find 'Seahawks' in top results.")

except Exception as e:
    print(f"Error: {e}")
