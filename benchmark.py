import asyncio
import time
from pathlib import Path
from coreason_ecosystem.orchestration.registry import calculate_epistemic_root


async def background_task():
    for _ in range(50):
        await asyncio.sleep(0.01)


async def run_benchmark():
    # Setup files
    project_path = Path("/tmp/coreason_benchmark")
    project_path.mkdir(exist_ok=True)
    schema = project_path / "coreason_ontology.schema.json"
    ledger_dir = project_path / ".coreason"
    ledger_dir.mkdir(exist_ok=True)
    ledger = ledger_dir / "capability_ledger.json"

    # Write some data
    schema.write_bytes(b"0" * 1024 * 1024 * 20)  # 20 MB
    ledger.write_bytes(b"1" * 1024 * 1024 * 20)  # 20 MB

    start = time.perf_counter()
    # Run multiple roots concurrently
    await asyncio.gather(
        calculate_epistemic_root(project_path),
        calculate_epistemic_root(project_path),
        calculate_epistemic_root(project_path),
        calculate_epistemic_root(project_path),
    )
    end = time.perf_counter()
    print(f"Time taken: {end - start:.4f} seconds")

    # cleanup
    schema.unlink()
    ledger.unlink()
    ledger_dir.rmdir()
    project_path.rmdir()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
