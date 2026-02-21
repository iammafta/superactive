import asyncio
import os
from arq import create_pool
from arq.connections import RedisSettings

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

async def main():
    print("Testing ARQ Redis enqueuing...")
    
    # 1. Connect to Redis
    try:
        redis_settings = RedisSettings(host=REDIS_HOST, port=REDIS_PORT)
        pool = await create_pool(redis_settings)
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        return

    # 2. Enqueue a fake job
    # Ensure campaign_id and tenant_id match existing DB rows if the worker 
    # attempts to load them, but for a ping test it enqueues successfully.
    try:
        job = await pool.enqueue_job(
            'dial_contact_task',
            "camp_test_queue",
            "tenant_test_queue",
            0,
            "+15551234567"
        )
        if job:
            print(f"✅ Enqueued job {job.job_id}")
            print("\nRun the worker in another terminal to see it process:")
            print("arq worker.WorkerSettings")
        else:
            print("❌ Failed to enqueue job (returned None)")
    except Exception as e:
        print(f"❌ Failed to enqueue job: {e}")

if __name__ == "__main__":
    asyncio.run(main())
