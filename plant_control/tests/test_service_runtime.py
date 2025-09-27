import asyncio
from asyncio.tasks import sleep
from plant_control.app.runtime.service_runtime import ServiceRuntime

async def main():
    runtime = ServiceRuntime(log_file_path="/tmp/service_runtime.txt")
    try:
        await runtime.start()
        tag_service = runtime.tag_service
        try:
            result = await tag_service.read_tag("EPS01", "HW_OL_T_RX04")
        except Exception as e:
            pass
    finally:
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())
