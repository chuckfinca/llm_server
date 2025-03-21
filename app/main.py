from fastapi import FastAPI
from contextlib import asynccontextmanager
from starlette.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.routes import main_router, health_router
from app.api.routes_programs import programs_router
from app.core.error_handling import handle_exception, validation_exception_handler
from app.models.manager import ModelManager
from app.models.program_manager import ProgramManager
from app.core import logging
from app.core.middleware import add_versioning_middleware
from fastapi.exceptions import RequestValidationError

logging.setup_logging() 

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize settings and model manager
    app.state.settings = get_settings()
    app.state.model_manager = ModelManager(app.state.settings.config_path)
    
    # Initialize program manager for DSPy program tracking
    app.state.program_manager = ProgramManager(app.state.model_manager)
    logging.info("Program manager initialized")
    
    yield
    
    # Clean up
    app.state.model_manager = None
    app.state.program_manager = None

app = FastAPI(lifespan=lifespan)
app.add_exception_handler(Exception, handle_exception)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add versioning middleware to enforce program/model versioning
add_versioning_middleware(app)

# Include health check routes (no authentication)
app.include_router(health_router)

# Include main API routes (with authentication)
app.include_router(main_router)

# Nest the programs router under the main router
main_router.include_router(programs_router)