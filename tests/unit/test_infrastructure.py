import os
import yaml
from pathlib import Path


def test_deployment_continuum_helm_values():
    """
    AGENT INSTRUCTION: Mathematically prove that the Deployment Continuum 
    (from USB Stick to Hyperscaler) is structurally sound by validating the Helm values.
    """
    base_dir = Path(__file__).parent.parent.parent
    helm_dir = base_dir / "infrastructure" / "helm" / "coreason-enterprise"
    
    prod_values_path = helm_dir / "values.yaml"
    local_values_path = helm_dir / "values-local.yaml"
    
    assert prod_values_path.exists(), "values.yaml is missing"
    assert local_values_path.exists(), "values-local.yaml is missing"
    
    with open(prod_values_path, "r") as f:
        prod_values = yaml.safe_load(f)
        
    with open(local_values_path, "r") as f:
        local_values = yaml.safe_load(f)
        
    # Verify Production Hyperscaler values
    assert prod_values["runtime"]["autoscaling"]["enabled"] is True, "HPA must be enabled in production."
    assert prod_values["runtime"]["autoscaling"]["maxReplicas"] >= 10, "Production must scale to at least 10 replicas."
    
    # Verify Local/Edge values
    assert local_values["global"]["environment"] == "local", "Local environment must be 'local'"
    assert local_values["runtime"]["autoscaling"]["enabled"] is False, "HPA must be disabled on the edge/laptop."
    assert local_values["runtime"]["replicaCount"] == 1, "Edge deployment must constrain replicas to 1."


def test_edge_compose_integrity():
    """
    AGENT INSTRUCTION: Mathematically prove the USB-Stick / Edge Compose file
    contains the required OTLP sidecars and Redpanda Connect fallbacks.
    """
    base_dir = Path(__file__).parent.parent.parent
    compose_path = base_dir / "infrastructure" / "local" / "compose.yaml"
    
    assert compose_path.exists(), "infrastructure/local/compose.yaml is missing"
    
    with open(compose_path, "r") as f:
        compose = yaml.safe_load(f)
        
    services = compose.get("services", {})
    
    assert "otel-collector" in services, "OTEL Collector sidecar is missing from Edge deployment"
    assert "redpanda-connect" in services, "Redpanda Connect is missing from Edge deployment"
    
    gateway_env = services["coreason-master-gateway"].get("environment", [])
    has_otlp_endpoint = any("COREASON_OTLP_ENDPOINT" in env_var for env_var in gateway_env)
    assert has_otlp_endpoint, "Master Gateway must have COREASON_OTLP_ENDPOINT pointing to sidecar"
