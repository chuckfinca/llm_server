import modal
import os

# Get environment from env var, defaulting to staging
ENVIRONMENT = os.getenv("ENVIRONMENT", "staging")
APP_NAME = f"llm-server-{ENVIRONMENT}"

# Create the modal_app
modal_app = modal.App(APP_NAME)

# Use existing Dockerfile
image = modal.Image.from_dockerfile("Dockerfile")

# Create volume for logs
volume = modal.Volume.from_name(f"{APP_NAME}-logs", create_if_missing=True)

# Define the web endpoint function
@modal_app.function(
    image=image,
    secrets=[ modal.Secret.from_name(f"llm-server-{ENVIRONMENT}-secrets")],
    volumes={"/data": volume},
    gpu="T4",
    memory=4096,
    timeout=600
)
@modal.asgi_app()
def fastapi_app():
    from app.main import app
    return app

# Create a healthcheck function
@modal_app.function(
    image=image,
    schedule=modal.Period(minutes=30)
)
def healthcheck():
    import requests
    response = requests.get("http://localhost:8000/health")
    assert response.status_code == 200
    print("Health check passed!")

if __name__ == "__main__":
    modal_app.run()