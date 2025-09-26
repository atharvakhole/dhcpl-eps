from ...app.core.tag_service import TagService
from ...app.config import config_manager
from ...app.core.connection_manager import connection_manager
from ...app.utilities.telemetry import logger


class ServiceRuntime:
    def __init__(self):
        self.config_manager = config_manager
        self.tag_service = None
        self.procedure_executor = None
        self.register_maps = None
        self.logger = logger


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
