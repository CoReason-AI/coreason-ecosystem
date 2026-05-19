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
    Spins up the ephemeral test environment using host-native Mock gateways and docker-compose.
    """
    # Start the host-native gateways as subprocesses to reflect new architecture
    processes = []
    print("\nStarting host-native mock components...")

    # 8101: Master Gateway
    processes.append(subprocess.Popen(["python", "-m", "http.server", "8101"]))
    # 8102: URN Authority
    processes.append(subprocess.Popen(["python", "-m", "http.server", "8102"]))
    # 8103: Meta Engineering
    processes.append(subprocess.Popen(["python", "-m", "http.server", "8103"]))

    # Start the cluster
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to start docker-compose: {e.stderr.decode()}")
        for p in processes:
            p.kill()
        raise e

    # Wait for the Master Gateway and Runtime to be healthy
    print("\nWaiting for Tripartite Swarm to become healthy...")
    max_retries = 30
    for i in range(max_retries):
        try:
            # Check Master Gateway (now running natively)
            res_gateway = httpx.get("http://localhost:8101/", timeout=1.0)
            # Check Runtime
            res_runtime = httpx.get("http://localhost:8100/docs", timeout=1.0)

            if res_gateway.status_code in [
                200,
                501,
                404,
            ] and res_runtime.status_code in [200, 501, 404]:
                print("Swarm is healthy and ready for testing.")
                break
        except httpx.RequestError:
            pass

        time.sleep(2)
    else:
        # If we exit the loop without breaking, we failed to start
        subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), "logs"])
        subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), "down"])
        for p in processes:
            p.kill()
        pytest.fail("Tripartite Swarm did not become healthy in time.")

    yield

    # Tear down the cluster and processes
    print("\nTeardown: Spinning down Tripartite Swarm...")
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"], check=True
    )
    for p in processes:
        p.kill()
