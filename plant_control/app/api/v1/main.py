from fastapi import FastAPI
from contextlib import asynccontextmanager

# Import your modules
from plant_control.app.core.tag_service import TagService
from plant_control.app.config import config_manager
from plant_control.app.core.connection_manager import connection_manager
from plant_control.app.utilities.telemetry import logger
from plant_control.app.core.health_service import HealthService
from plant_control.app.core.procedure_execution_engine import ProcedureExecutor

from plant_control.app.api.v1.router import api_router
from plant_control.app.core.exceptions import setup_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    try:
        # Startup
        logger.info("Initializing PLC connections...")
        plc_configs = config_manager.load_plc_configs()
        register_maps = config_manager.load_register_maps()
        await connection_manager.initialize(plc_configs, config_manager)
        
        # Initialize services
        global plc_handler, health_service, procedure_executor
        plc_handler = TagService()
        health_service = HealthService()
        
        # Load procedures after PLC configs and register maps are loaded
        try:
            procedures = config_manager.load_procedures()
            logger.info(f"Loaded {len(procedures)} procedures")
        except Exception as e:
            logger.warning(f"Failed to load procedures: {e}")
            # Continue startup even if no procedures are loaded
        
        # Initialize procedure executor
        procedure_executor = ProcedureExecutor(plc_handler)
        
        logger.info("All services initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down services...")
        # await connection_manager.shutdown()  # if you have cleanup logic


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(title="PLC Tag API", version="1.0.0", lifespan=lifespan)
    
    # Setup exception handlers
    setup_exception_handlers(app)
    
    # Include routers
    app.include_router(api_router)
    
    return app


# Global service instances (initialized during lifespan startup)
plc_handler = None
health_service = None
procedure_executor = None
