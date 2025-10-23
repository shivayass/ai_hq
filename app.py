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
    prompt = data.get("prompt", "")

    # Model + token
    hf_model = os.getenv("HF_MODEL", "google/flan-t5-base")
    hf_token = os.getenv("HF_TOKEN")

    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{hf_model}",
            headers={"Authorization": f"Bearer {hf_token}"},
            json={"inputs": prompt},
        )

        # Debug output
        print("DEBUG Hugging Face response:", response.text)

        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and "generated_text" in result[0]:
                return {"reply": result[0]["generated_text"]}
            else:
                return {"raw_result": result}
        else:
            return {
                "error": f"Hugging Face API returned {response.status_code}",
                "details": response.text,
            }

    except Exception as e:
        return {"error": f"Internal error: {str(e)}"}

@app.get("/debug-env")
def debug_env():
    """Shows active model info for debugging"""
    return {
        "HF_MODEL": HF_MODEL,
        "FALLBACK_MODEL": FALLBACK_MODEL,
        "API_URL": API_URL
    }
