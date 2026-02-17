import requests
import sys
import os

def trigger_outbound_call(to_number, agent_id="birthday_promo", public_url=None):
    """Trigger an outbound call via the local API."""
    base_url = "http://localhost:8765"
    
    # If public URL is provided, we might need to update the server env or pass it
    # But server.py reads env. We can try to patch it or just assume the user
    # updated the .env or exported the var before running server.
    
    payload = {
        "to": to_number,
        "agent_id": agent_id
    }
    
    print(f"📞 Triggering outbound call to {to_number} using agent '{agent_id}'...")
    try:
        resp = requests.post(f"{base_url}/api/outbound-call", json=payload)
        resp.raise_for_status()
        print("✅ Call initiated successfully!")
        print(f"Response: {resp.json()}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to trigger call: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Server replied: {e.response.text}")
        else:
            print("Is the server running on port 8765?")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trigger_call.py <phone_number> [agent_id]")
        sys.exit(1)
        
    phone = sys.argv[1]
    agent = sys.argv[2] if len(sys.argv) > 2 else "birthday_promo"
    
    trigger_outbound_call(phone, agent)
