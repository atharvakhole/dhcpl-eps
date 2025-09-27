import asyncio
from asyncio.tasks import sleep
from plant_control.app.runtime.service_runtime import ServiceRuntime

async def main():
    runtime = ServiceRuntime()
    try:
        await runtime.start()
        tag_service = runtime.tag_service
        try:
            result = await tag_service.read_tag("EPS01", "HW_OL_T_RX04")
            print(result)
        except Exception as e:
            print(e)
    finally:
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())
