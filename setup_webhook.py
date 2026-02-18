import os
import sys
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

# Configuration
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
phone_number = os.getenv("TWILIO_PHONE_NUMBER")
ngrok_url = os.getenv("PUBLIC_URL", "https://carlena-unadmonished-translationally.ngrok-free.dev")

if not all([account_sid, auth_token, phone_number]):
    print("Error: Missing Twilio credentials in .env")
    sys.exit(1)

client = Client(account_sid, auth_token)

print(f"Searching for phone number: {phone_number}...")

try:
    # Find the phone number SID
    incoming_phone_numbers = client.incoming_phone_numbers.list(phone_number=phone_number, limit=1)
    
    if not incoming_phone_numbers:
        print(f"Error: Phone number {phone_number} not found in your Twilio account.")
        sys.exit(1)

    number_sid = incoming_phone_numbers[0].sid
    print(f"Found SID: {number_sid}")

    # Update Voice URL
    voice_url = f"{ngrok_url}/incoming-call"
    print(f"Updating Voice URL to: {voice_url}")

    client.incoming_phone_numbers(number_sid).update(
        voice_url=voice_url,
        voice_method="POST"  # Though WebSocket upgrade happens, initial request is POST/GET
    )
    
    print("Success! Webhook updated.")

except Exception as e:
    print(f"Error updating webhook: {e}")
    sys.exit(1)
