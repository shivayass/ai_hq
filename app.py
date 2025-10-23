import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "tiiuae/falcon-7b-instruct")  # your main model
FALLBACK_MODEL = "facebook/blenderbot-400M-distill"  # free hosted backup

API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

@app.get("/")
def home():
    return {"message": "AI HQ is live! Send POST request to /chat"}

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "Hello, who are you?")
    payload = {"inputs": prompt}

    # Step 1: Try the main model
    response = requests.post(API_URL, headers=HEADERS, json=payload)

    # Step 2: If 404 or error, auto fallback
    if response.status_code != 200:
        print(f"[WARN] Main model failed ({response.status_code}), switching to fallback.")
        fallback_url = f"https://api-inference.huggingface.co/models/{FALLBACK_MODEL}"
        response = requests.post(fallback_url, headers=HEADERS, json=payload)

    # Step 3: Return the model’s reply
    try:
        result = response.json()
        if isinstance(result, list) and len(result) > 0 and "generated_text" in result[0]:
            return {"reply": result[0]["generated_text"]}
        elif "error" in result:
            return {"error": result["error"]}
        else:
            return result
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/debug-env")
def debug_env():
    """Shows active model info for debugging"""
    return {
        "HF_MODEL": HF_MODEL,
        "FALLBACK_MODEL": FALLBACK_MODEL,
        "API_URL": API_URL
    }
