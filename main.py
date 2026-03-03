import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
from google import genai
from google.genai import types
from google.cloud import firestore

app = FastAPI(title="LingoLoom Backend")

# 1. Initialize Gemini
client = genai.Client()

# 2. Initialize Firestore (Cloud Run handles the security automatically!)
db = firestore.Client()

SYSTEM_PROMPT = """
You are a creative and encouraging English phonics tutor for children. 
You are hosting an interactive storybook adventure. 
Whenever you tell a story, you MUST always include two recurring characters: a green explorer and an orange explorer. 
Keep your responses brief, enthusiastic, and highly interactive.
"""

@app.get("/")
async def root():
    return {"message": "LingoLoom AI Brain and Database are online!"}

@app.websocket("/ws/tutor")
async def websocket_tutor(websocket: WebSocket):
    await websocket.accept()
    print("Mobile client connected to LingoLoom!")
    
    # 3. Create a user session in Firestore when they connect
    session_id = "demo_user_001" 
    session_ref = db.collection("sessions").document(session_id)
    session_ref.set({
        "status": "connected",
        "earned_badges": [] # We will append to this array later!
    }, merge=True)
    print(f"Firestore session initialized for {session_id}")
    
    try:
        # Connect to the Gemini Multimodal Live API
        async with client.aio.live.connect(
            model="gemini-2.0-flash",
            config=types.LiveConnectConfig(
                system_instruction=types.Content(parts=[types.Part.from_text(SYSTEM_PROMPT)])
            )
        ) as session:
            print("Connected to Gemini Live API!")

            async def receive_from_gemini():
                async for response in session.receive():
                    if response.server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.text:
                                await websocket.send_json({
                                    "type": "text",
                                    "data": part.text
                                })

            async def send_to_gemini():
                try:
                    while True:
                        data = await websocket.receive_text()
                        print(f"User said: {data}")
                        await session.send(input=data, end_of_turn=True)
                except WebSocketDisconnect:
                    print("Client disconnected")

            await asyncio.gather(
                receive_from_gemini(),
                send_to_gemini()
            )

    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)