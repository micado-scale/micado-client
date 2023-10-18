CONFIGS: dict = {
    "hosts": ("playbook/inventory", "hosts", ".yml"),
    "cloud": ("playbook/project/credentials", "credentials-cloud-api", ".yml"),
    "registry": ("playbook/project/credentials", "credentials-registries", ".yml"),
    "web": ("playbook/project/credentials", "credentials-micado", ".yml"),
    "settings": ("playbook/project/host_vars", "micado", ".yml"),
}

DEMOS: dict = {
    "stressng": ("demos/stressng", "stressng", ".yaml"),
    "nginx": ("demos/nginx", "nginx", ".yaml"),
    "wordpress": ("demos/wordpress", "wordpress", ".yaml"),
    "cqueue": ("demos/cqueue", "cqueue", ".yaml"),
}

CLOUDS: list = [
    "ec2",
    "azure",
    "gcp",
    "oci",
    "nova",
    "cloudsigma",
    "cloudbroker",
]

warned_vault = ".user_warned_vault"