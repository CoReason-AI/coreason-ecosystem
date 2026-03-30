# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import asyncio
import time
from unittest.mock import patch, AsyncMock
from coreason_ecosystem.orchestration.sync import execute_sync


async def monitor_event_loop() -> float:
    max_block = 0.0
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < 2.0:  # Monitor for 2 seconds
        loop_start = time.perf_counter()
        await asyncio.sleep(0.01)
        block = time.perf_counter() - loop_start - 0.01
        if block > max_block:
            max_block = block
    return max_block


async def main() -> None:
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
