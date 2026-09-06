import os


def get_secret(env_name: str, vault_secret_name: str) -> str | None:
    """Prefer local/environment injection; fall back to managed-identity Key Vault access."""
    if value := os.getenv(env_name):
        return value
    vault_uri = os.getenv("KEY_VAULT_URI")
    if not vault_uri:
        return None
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    return SecretClient(vault_url=vault_uri, credential=DefaultAzureCredential()).get_secret(
        vault_secret_name
    ).value
