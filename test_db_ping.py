import asyncio
import asyncpg
import redis.asyncio as aioredis
import os

POSTGRES_USER = os.getenv("POSTGRES_USER", "superactive")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "superactive")
POSTGRES_DB = os.getenv("POSTGRES_DB", "superactive")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")

async def check_postgres():
    print(f"Testing Postgres at postgres://{POSTGRES_USER}:***@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB} ...")
    try:
        conn = await asyncpg.connect(
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT
        )
        version = await conn.fetchval('SELECT version()')
        print(f"✅ Postgres connection successful! Version: {version}")
        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Postgres connection failed: {e}")
        return False

async def check_redis():
    print(f"Testing Redis at redis://{REDIS_HOST}:{REDIS_PORT} ...")
    try:
        # ARQ uses aioredis (now part of redis-py in modern versions, but arq abstracts it)
        # For a simple ping without arq overhead, we'll try to connect directly using standard redis or aioredis.
        # However, to avoid needing to install another library just for this test, we can use simple asyncio routing
        reader, writer = await asyncio.open_connection(REDIS_HOST, REDIS_PORT)
        writer.write(b"*1\r\n$4\r\nPING\r\n")
        await writer.drain()
        response = await reader.read(100)
        writer.close()
        await writer.wait_closed()
        
        if b"PONG" in response:
            print("✅ Redis connection successful!")
            return True
        else:
            print(f"❌ Redis connection returned unexpected response: {response}")
            return False
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

async def main():
    print("--- Starting Service Connectivity Checks ---")
    pg_ok = await check_postgres()
    redis_ok = await check_redis()
    
    if pg_ok and redis_ok:
        print("\n🎉 All services are up and running!")
    else:
        print("\n⚠️ Some services failed to connect. Check Docker Desktop.")

if __name__ == "__main__":
    asyncio.run(main())
