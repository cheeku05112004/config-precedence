import os
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}


def read_dotenv():
    result = {}
    path = Path(".env")

    if not path.exists():
        return result

    for line in path.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip("'\"")

    return result


def normalize_key(key):
    key = key.strip().lower()

    if key.startswith("app_"):
        key = key[4:]

    if key == "num_workers":
        key = "workers"

    return key


def convert_value(key, value):
    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        return str(value).strip().lower() in (
            "true", "1", "yes", "on"
        )

    return str(value)


@app.get("/effective-config")
def effective_config(request: Request):
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    env_name = os.environ.get("APP_ENV", "development")
    yaml_path = Path(f"config.{env_name}.yaml")

    if yaml_path.exists():
        with yaml_path.open(encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}

        for key, value in yaml_config.items():
            config[normalize_key(key)] = value

    # Layer 3: .env file
    for key, value in read_dotenv().items():
        normalized = normalize_key(key)
        if normalized in ("port", "workers", "debug",
                          "log_level", "api_key"):
            config[normalized] = value

    # Layer 4: OS environment variables with APP_ prefix
    for key, value in os.environ.items():
        if key.startswith("APP_") and key != "APP_ENV":
            normalized = normalize_key(key)
            if normalized in ("port", "workers", "debug",
                              "log_level", "api_key"):
                config[normalized] = value

    # Layer 5: CLI-style query overrides
    for item in request.query_params.getlist("set"):
        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        normalized = normalize_key(key)

        if normalized in ("port", "workers", "debug",
                          "log_level", "api_key"):
            config[normalized] = value

    # Apply required types and always mask the secret
    result = {
        key: convert_value(key, config[key])
        for key in ("port", "workers", "debug", "log_level")
    }
    result["api_key"] = "****"

    return result
