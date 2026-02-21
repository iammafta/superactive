from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

for n in client.notifications.list(limit=5):
    print(f"Date: {n.message_date}, Error code: {n.error_code}, Message: {n.message_text}")
    print(f"URL: {n.request_url}, Body: {n.response_body}")
    print("---")
