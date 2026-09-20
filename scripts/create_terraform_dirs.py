import os
import textwrap

base = "infra/terraform"

dirs = [
    "modules/networking",
    "modules/kubernetes",
    "modules/postgresql",
    "modules/redis",
    "modules/container-registry",
    "modules/monitoring",
    "environments/dev",
    "environments/staging",
    "environments/production",
    "tests",
]

for d in dirs:
    os.makedirs(os.path.join(base, d), exist_ok=True)

print("directories created")