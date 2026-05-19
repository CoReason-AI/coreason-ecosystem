import pytest
import subprocess
import time
import httpx
from pathlib import Path

# Paths
E2E_DIR = Path(__file__).parent
COMPOSE_FILE = E2E_DIR / "docker-compose.e2e.yaml"


@pytest.fixture(scope="session", autouse=True)
def spin_up_tripartite_swarm():
    """
    Spins up the ephemeral test environment using docker-compose.
    This strictly adheres to the 'Anti-Mocking' directive by using real containers.
    """
    # Start the cluster
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to start docker-compose: {e.stderr.decode()}")
        raise e

    # Wait for the Master Gateway and Runtime to be healthy
    print("\nWaiting for Tripartite Swarm to become healthy...")
    max_retries = 30
    for i in range(max_retries):
        try:
            # Check Master Gateway
            res_gateway = httpx.get("http://localhost:8001/", timeout=1.0)
            # Check Runtime
            res_runtime = httpx.get("http://localhost:8000/docs", timeout=1.0)

            if res_gateway.status_code == 200 and res_runtime.status_code == 200:
                print("Swarm is healthy and ready for testing.")
                break
        except httpx.RequestError:
            pass

        time.sleep(2)
    else:
        # If we exit the loop without breaking, we failed to start
        subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), "logs"])
        subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), "down"])
        pytest.fail("Tripartite Swarm did not become healthy in time.")

    yield

    # Tear down the cluster
    print("\nTeardown: Spinning down Tripartite Swarm...")
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"], check=True
    )
