from plant_control.app.core.tag_service import TagService
from plant_control.app.config import config_manager
from plant_control.app.core.connection_manager import connection_manager
from plant_control.app.utilities.logging_examples import setup_file_logging
from plant_control.app.utilities.telemetry import logger


class ServiceRuntime:
    def __init__(self, log_file_path: str, enable_console: bool=False):
        self.config_manager = config_manager
        self.tag_service = None
        self.procedure_executor = None
        self.register_maps = None
        self.logger = setup_file_logging(log_file_path, enable_console)


    async def start(self):
        logger.info("Initializing PLC connections...")
        plc_configs = self.config_manager.load_plc_configs()
        self.register_maps = self.config_manager.load_register_maps()
        await connection_manager.initialize(plc_configs, self.config_manager)

        self.tag_service = TagService()
        logger.info("All services initialized successfully")

    async def stop(self):
        logger.info("Shutting down services...")
        await connection_manager.shutdown()
