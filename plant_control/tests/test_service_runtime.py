import signal
import time
from plant_control.app.runtime.service_manager import service_manager
from plant_control.app.runtime.service_runtime import ServiceRuntime

def main():
    """Main function - now completely synchronous!"""
    runtime = ServiceRuntime(log_file_path="/tmp/service_runtime.txt", enable_console=True)
    
    try:
        print("Starting background service...")
        service_manager.start_background_service(runtime)
        
        print("Testing tag operations...")
        
        # Now you can use sync calls!
        try:
            result = service_manager.read_tag("PLC1_SIMULATOR", "CONVEYOR_SP", timeout=10.0)
            print(f"Tag read result: {result}")
        except Exception as e:
            print(f"Tag read failed: {e}")
        
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
