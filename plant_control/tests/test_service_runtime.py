import signal
import time
from plant_control.app.runtime.service_manager import service_manager
from plant_control.app.runtime.service_runtime import ServiceRuntime
from plant_control.app.utilities.logging_config import LogLevel

def main():
    """Main function - now completely synchronous!"""
    runtime = ServiceRuntime(log_file_path="/tmp/service_runtime.txt", enable_console=True, log_level=LogLevel.INFO)
    
    try:
        print("Starting background service...")
        service_manager.start_background_service(runtime)
        
        print("Testing tag operations...")
        
        # Now you can use sync calls!
        print(service_manager.write_tag("PLC1_SIMULATOR", "CONVEYOR_SP", 300))
        print(service_manager.write_tag("PLC1_SIMULATOR", "TEMPERATURE_SP", 55))
        print(service_manager.write_tag("PLC1_SIMULATOR", "MOTOR_CURRENT_LIMIT", 23))
        print(service_manager.write_tag("PLC1_SIMULATOR", "PR_TARGET", 1000))
        
        # You can do multiple operations
        try:
            # Example write operation
            # write_result = service_manager.write_tag("EPS01", "SOME_TAG", 42, timeout=10.0)
            # print(f"Tag write result: {write_result}")
            pass
        except Exception as e:
            print(f"Tag write failed: {e}")
        
        print("Service is running. Press Ctrl+C to stop or wait...")
        
        # Keep running - you can add your application logic here
        # This is where you'd normally have your main application loop
        try:
            while True:
                time.sleep(1)
                # Your application logic here
                # You can call service_manager.read_tag() or write_tag() anytime
        except KeyboardInterrupt:
            print("\nReceived keyboard interrupt...")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Stopping background service...")
        service_manager.stop_background_service()
        print("Application terminated.")

if __name__ == "__main__":
    main()  # Notice: no asyncio.run() needed!
