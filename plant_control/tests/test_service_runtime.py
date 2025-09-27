import asyncio
from plant_control.app.runtime.service_manager import service_manager
from plant_control.app.runtime.service_runtime import ServiceRuntime

async def main():
    runtime = ServiceRuntime(log_file_path="/tmp/service_runtime.txt", enable_console=False)
    try:
        await runtime.start()
        try:
            print("HERE")
            result = service_manager.read_tag("EPS01", "HW_OL_T_RX04")
            print(result)
        except Exception as e:
            print(e)
    finally:
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())
