CONFIGS: dict = {
    "hosts": ("playbook/inventory", "hosts", ".yml"),
    "cloud": ("playbook/project/credentials", "credentials-cloud-api", ".yml"),
    "registry": ("playbook/project/credentials", "credentials-registries", ".yml"),
    "web": ("playbook/project/credentials", "credentials-micado", ".yml"),
    "settings": ("playbook/project/host_vars", "micado", ".yml"),
}

warned_vault = ".user_warned_vault"