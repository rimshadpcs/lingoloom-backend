import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

app = FastAPI(title="LingoLoom Backend")
# Testing the CI/CD pipeline
@app.get("/")
async def root():
    return {"message": "LingoLoom API is running! Your backend is alive."}

@app.websocket("/ws/tutor")
async def websocket_tutor(websocket: WebSocket):
    await websocket.accept()
    print("Mobile client connected to LingoLoom!")
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received from client: {data}")
            
            # Send a test response back
            await websocket.send_json({
                "type": "text",
                "data": "Hello from your Python backend!"
            })
                
    except WebSocketDisconnect:
        print("Mobile client disconnected")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)