from fastapi import FastAPI
import modal
import os
from pathlib import Path

# Create secrets
app_secrets = modal.Secret.from_name("app-secrets")

# Base app name
APP_NAME = "llm-server"

# Create the modal_app
modal_app = modal.App(APP_NAME)

ENV_NAME = os.getenv('APP_ENV', 'development')
VOLUME_NAME = f"llm-server-{ENV_NAME}-logs"

# Create image with requirements file and install packages
requirements_path = Path(__file__).parent / "requirements.txt"
image = (
    modal.Image.debian_slim(python_version="3.9")
    .copy_local_file(requirements_path, remote_path="/root/requirements.txt")
    .run_commands("pip install -r /root/requirements.txt")
    .copy_local_dir(".", remote_path="/app")
)

# Create volume for logs
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

@modal_app.function(
    image=image,
    secrets=[app_secrets],
    volumes={"/data": volume},
    gpu="T4",
    memory=4096,
    timeout=600
)
@modal.asgi_app()
def fastapi_app():
    # from app.main import app
    return FastAPI()

if __name__ == "__main__":
    modal_app.serve()