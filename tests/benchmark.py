import asyncio
import time
from unittest.mock import patch, AsyncMock
from coreason_ecosystem.orchestration.sync import execute_sync


async def monitor_event_loop():
    max_block = 0
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < 2.0:  # Monitor for 2 seconds
        loop_start = time.perf_counter()
        await asyncio.sleep(0.01)
        block = time.perf_counter() - loop_start - 0.01
        if block > max_block:
            max_block = block
    return max_block


async def main():
    with patch(
        "coreason_ecosystem.orchestration.sync.execute_build", new_callable=AsyncMock
    ):
        start = time.perf_counter()

        monitor_task = asyncio.create_task(monitor_event_loop())
        # Add a slight delay to let monitor start
        await asyncio.sleep(0.05)

        await execute_sync()
        end = time.perf_counter()

        max_block = await monitor_task

        print("\n--- Benchmark Results ---")
        print(f"Total execute_sync time: {end - start:.4f}s")
        print(f"Max event loop block time: {max_block:.4f}s")
        print("-------------------------\n")


if __name__ == "__main__":
    asyncio.run(main())
