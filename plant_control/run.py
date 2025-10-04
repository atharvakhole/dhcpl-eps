import uvicorn
from plant_control.app.api.v1.server import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
