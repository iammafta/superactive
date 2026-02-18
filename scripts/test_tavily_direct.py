import os
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("TAVILY_API_KEY")
print(f"Testing Tavily with key: {api_key[:8]}...")

if not api_key:
    print("❌ No API key found!")
    exit(1)

try:
    client = TavilyClient(api_key=api_key)
    response = client.search(query="Who won the Super Bowl in 2024?", search_depth="basic", max_results=1)
    
    print("\n✅ Tavily Response Received:")
    print(response)
    
    if "results" in response and response["results"]:
        print(f"\nResult 1: {response['results'][0]['title']}")
    else:
        print("\n⚠️ No results in response list.")

except Exception as e:
    print(f"\n❌ Tavily Error: {e}")
