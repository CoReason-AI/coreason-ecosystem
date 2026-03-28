import asyncio
import time
from pathlib import Path
from coreason_ecosystem.orchestration.init import execute_init
import shutil


async def run_bench():
    start = time.perf_counter()
    tasks = []
    for i in range(20):
        project_name = f"test_bench_{i}"
        if Path(project_name).exists():
            shutil.rmtree(project_name)
        tasks.append(execute_init(project_name, topology="base"))

    await asyncio.gather(*tasks)
    end = time.perf_counter()
    print(f"Time: {end - start:.4f}s")

    for i in range(20):
        project_name = f"test_bench_{i}"
        if Path(project_name).exists():
            shutil.rmtree(project_name)


if __name__ == "__main__":
    asyncio.run(run_bench())
