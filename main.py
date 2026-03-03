import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
from google import genai
from google.genai import types
from google.cloud import firestore

app = FastAPI(title="LingoLoom Backend")

client = genai.Client()
db = firestore.Client()

SYSTEM_PROMPT = """
You are a highly energetic and encouraging English phonics tutor for children, hosting an interactive, cozy, and magical storybook adventure.

Whenever you tell a story, you MUST center it around two recurring best friends: a fun, bouncy Green Dinosaur and a brave, playful Orange Dinosaur. They love exploring their cozy world and finding objects that start with the phonics letter of the day.

Keep your verbal responses brief (1 to 2 sentences at a time), extremely enthusiastic, and highly interactive. Always ask the child a simple question or ask them to repeat a sound.

CRITICAL INSTRUCTION: When the child correctly pronounces a sound or answers a question, you MUST immediately use the `award_mastery_badge` tool to give them a reward. When you do, enthusiastically describe handing them a special mastery badge. Describe this badge as a cozy, chunky little storybook with a distinct, where the cover proudly displays the exact letter they just learned, perfectly matching the warm, inviting world of the dinosaurs.
"""

# 1. Define the Tool (Giving Gemini "hands")
award_badge_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="award_mastery_badge",
            description="Awards a mastery badge to the user for completing a phonics milestone.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "milestone_name": types.Schema(
                        type=types.Type.STRING, 
                        description="The name of the milestone, e.g., 'Letter C Master'"
                    )
                },
                required=["milestone_name"]
            )
        )
    ]
)

@app.get("/")
async def root():
    return {"message": "LingoLoom Agentic Brain is online!"}

@app.websocket("/ws/tutor")
async def websocket_tutor(websocket: WebSocket):
    await websocket.accept()
    
    session_id = "demo_user_001" 
    session_ref = db.collection("sessions").document(session_id)
    session_ref.set({
        "status": "connected",
        "earned_badges": [] 
    }, merge=True)
    
    try:
        # 2. Add the tool to the Live API config
        async with client.aio.live.connect(
            model="gemini-2.0-flash",
            config=types.LiveConnectConfig(
                system_instruction=types.Content(parts=[types.Part.from_text(SYSTEM_PROMPT)]),
                tools=[award_badge_tool] # Injecting the tool here!
            )
        ) as session:

            async def receive_from_gemini():
                async for response in session.receive():
                    # Handle normal text/audio speaking
                    if response.server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.text:
                                await websocket.send_json({
                                    "type": "text",
                                    "data": part.text
                                })
                    
                    # 3. Handle the Tool Call! 
                    if response.tool_call:
                        for function_call in response.tool_call.function_calls:
                            if function_call.name == "award_mastery_badge":
                                milestone = function_call.args["milestone_name"]
                                print(f"AGENT ACTION: Awarding thick black-edged badge for {milestone}")
                                
                                # Update Firestore to trigger the Android UI
                                session_ref.update({
                                    "earned_badges": firestore.ArrayUnion([milestone])
                                })
                                
                                # Send a direct message to Compose to play the animation
                                await websocket.send_json({
                                    "type": "tool_action",
                                    "action": "badge_awarded",
                                    "data": milestone
                                })
                                
                                # Tell Gemini the tool succeeded so it can continue talking
                                await session.send(
                                    input=types.LiveClientContent(
                                        tool_response=types.ToolResponse(
                                            function_responses=[
                                                types.FunctionResponse(
                                                    name="award_mastery_badge",
                                                    response={"result": "Success. Badge added to database."}
                                                )
                                            ]
                                        )
                                    )
                                )

            async def send_to_gemini():
                try:
                    while True:
                        data = await websocket.receive_text()
                        await session.send(input=data, end_of_turn=True)
                except WebSocketDisconnect:
                    pass

            await asyncio.gather(receive_from_gemini(), send_to_gemini())

    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)