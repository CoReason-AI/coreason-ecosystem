import os

import hvac


def get_vault_client() -> hvac.Client:
    vault_url = os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
    vault_token = os.environ.get("VAULT_TOKEN", "dev-only-token")
    return hvac.Client(url=vault_url, token=vault_token)


def set_identity(tenant_cid: str, legal_name: str) -> None:
    """Stores the tenant identity securely into Vault."""
    client = get_vault_client()
    try:
        payload = {"tenant_cid": tenant_cid, "legal_name": legal_name}
        client.secrets.kv.v2.create_or_update_secret(
            path="coreason/identity",
            secret=payload,
        )
    except hvac.exceptions.InvalidPath:
        raise ValueError("Vault KV engine not properly configured at 'secret/'.")
    except hvac.exceptions.VaultError as e:
        raise ValueError(f"Failed to securely store identity in Vault: {e}")


def get_identity() -> dict[str, str] | None:
    """Retrieves the tenant identity from Vault."""
    client = get_vault_client()
    try:
        response = client.secrets.kv.v2.read_secret_version(
            path="coreason/identity", raise_on_deleted_version=False
        )
        if response and "data" in response and "data" in response["data"]:
            return response["data"]["data"]
        return None
    except Exception:
        return None
