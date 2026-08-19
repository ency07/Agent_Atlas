from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
import psutil
import time
from datetime import datetime

app = FastAPI(title="AEGIS-JARVIS Bridge")

class AIUsageResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_used: str
    tokens_used: int
    avg_response_time: float

class HealthResponse(BaseModel):
    status: str
    mcp_endpoints: dict
    timestamp: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    mcp_status = {
        "orchestrator": False,
        "guardian": False,
        "health": False,
        "memory": False,
        "windows": False,
        "corel_draw": False,
        "playwright": False
    }
    status = "degraded" if not any(mcp_status.values()) else "healthy"
    return HealthResponse(
        status=status,
        mcp_endpoints=mcp_status,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )

@app.get("/system_metrics")
async def system_metrics():
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('C:\\').percent
    return {"cpu": cpu, "ram": ram, "disk": disk, "timestamp": datetime.utcnow().isoformat()}

@app.get("/ai_usage", response_model=AIUsageResponse)
async def ai_usage():
    return AIUsageResponse(model_used="auto (orchestrator)", tokens_used=1234, avg_response_time=1.2)

@app.post("/execute_action")
async def execute_action(action: str):
    return {"status": "success", "message": f"Action '{action}' queued for execution"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bridge:app", host="127.0.0.1", port=8765)
