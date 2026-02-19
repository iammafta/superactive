import asyncio
from auth import verify_password
from db import db_get_user_by_email

async def main():
    user = await db_get_user_by_email("test@superactive.ai")
    print("User found:", user is not None)
    if user:
        print("Hash:", user["password_hash"])
        match = verify_password("supersecretpassword", user["password_hash"])
        print("Match?", match)

asyncio.run(main())
