ai_hq/main.py

FastAPI-based orchestrator (starter) for "AI HQ" - connects multiple AI services via APIs

Structure (single-file starter, expand to modules for production)

from fastapi import FastAPI, HTTPException, Request from pydantic import BaseModel import os import httpx import logging from typing import Optional, Dict, Any

app = FastAPI(title="AI-HQ Orchestrator") logging.basicConfig(level=logging.INFO)

---------- CONFIG: load from env ----------

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')  # e.g., Vertex/Gemini CANVA_API_KEY = os.getenv('CANVA_API_KEY') NOTION_API_KEY = os.getenv('NOTION_API_KEY') ONFIDO_API_KEY = os.getenv('ONFIDO_API_KEY') GOOGLE_SHEETS_CREDENTIALS = os.getenv('GOOGLE_SHEETS_CREDENTIALS') REPLICATE_API_KEY = os.getenv('REPLICATE_API_KEY')  # for image generation (optional)

Basic validation helper

if not OPENAI_API_KEY: logging.warning('OPENAI_API_KEY not set. Add it to .env before using LLM features')

---------- Request models ----------

class WorkflowRequest(BaseModel): user_id: Optional[str] = None prompt: str user_data: Optional[Dict[str, Any]] = None workflow: Optional[str] = None  # name of pre-defined workflow

---------- Utility: call OpenAI-compatible LLM (generic) ----------

async def call_openai_chat(prompt: str, system: Optional[str] = None, max_tokens: int = 600): if not OPENAI_API_KEY: raise RuntimeError('OpenAI API key missing')

url = 'https://api.openai.com/v1/chat/completions'
headers = {
    'Authorization': f'Bearer {OPENAI_API_KEY}',
    'Content-Type': 'application/json'
}
data = {
    'model': os.getenv('OPENAI_MODEL','gpt-4o-mini'),
    'messages': [
        {'role':'system','content': system or 'You are an expert assistant.'},
        {'role':'user','content': prompt}
    ],
    'max_tokens': max_tokens,
    'temperature': float(os.getenv('LLM_TEMPERATURE',0.2))
}
async with httpx.AsyncClient(timeout=30.0) as client:
    r = await client.post(url, json=data, headers=headers)
    r.raise_for_status()
    j = r.json()
    # adapt as needed; return raw JSON and a friendly string
    text = ''
    try:
        text = j['choices'][0]['message']['content']
    except Exception:
        text = str(j)
    return {'raw': j, 'text': text}

---------- Utility: call Vertex/Gemini (placeholder) ----------

async def call_vertex(prompt: str): # Placeholder: many users will use Google Vertex AI (Gemini) via REST # You must set up service account and use OAuth2; here we provide a stub if not GOOGLE_API_KEY: return {'error':'GOOGLE_API_KEY not set', 'text':''} return {'raw': {}, 'text': 'Vertex call placeholder — integrate with service account.'}

---------- Utility: call Canva Design API (placeholder) ----------

async def call_canva_design(instruction: str): if not CANVA_API_KEY: return {'error':'CANVA_API_KEY not set'} # Canva has a REST API — adapt payload per their docs return {'raw': {}, 'result_url': 'https://canva.com/project/placeholder'}

---------- Utility: call Onfido KYC (placeholder) ----------

async def call_onfido_kyc(user_data: Dict[str,Any]): if not ONFIDO_API_KEY: return {'error':'ONFIDO_API_KEY not set'} # Onfido flow: create applicant -> upload document -> check return {'raw': {}, 'status': 'ok', 'score': 'low-risk-placeholder'}

---------- Utility: generate image via Replicate or other provider ----------

async def call_image_gen(prompt: str): if not REPLICATE_API_KEY: return {'error':'REPLICATE_API_KEY not set'} # Example using Replicate: https://replicate.com/docs url = 'https://api.replicate.com/v1/predictions' headers = {'Authorization': f'Token {REPLICATE_API_KEY}', 'Content-Type':'application/json'} data = { 'version': 'stable-diffusion-v1', 'input': {'prompt': prompt} } async with httpx.AsyncClient(timeout=60.0) as client: r = await client.post(url, json=data, headers=headers) r.raise_for_status() return r.json()

---------- Orchestration endpoint ----------

@app.post('/run-workflow') async def run_workflow(req: WorkflowRequest): try: # 1) LLM: analyze prompt and produce a plan plan_prompt = f"You are an expert business advisor. User asked: {req.prompt}\nProduce: summary, 3 business ideas, estimated costs, recommended AI tools to execute, next actions." llm1 = await call_openai_chat(plan_prompt)

# 2) Optional: call Vertex for real-time trend checks (if set up)
    vertex = await call_vertex(req.prompt)

    # 3) If user requested visuals or logo, call image API
    image_result = None
    if 'logo' in req.prompt.lower() or 'logo' in (req.workflow or '').lower():
        image_result = await call_image_gen(f"Logo design for: {req.prompt}")

    # 4) If user_data present and has id fields, call KYC
    kyc = None
    if req.user_data and ('id_number' in req.user_data or 'id_image' in req.user_data):
        kyc = await call_onfido_kyc(req.user_data)

    # 5) Draft marketing copy via LLM
    marketing_prompt = f"Create a 30s ad script, 3 social captions, and 5 hashtags for: {req.prompt}"
    marketing = await call_openai_chat(marketing_prompt)

    # 6) Package and return
    result = {
        'analysis': llm1['text'],
        'vertex_check': vertex,
        'image': image_result,
        'kyc': kyc,
        'marketing': marketing['text']
    }
    return {'status':'ok', 'result': result}

except httpx.HTTPStatusError as httpe:
    logging.exception('HTTP error')
    raise HTTPException(status_code=502, detail=str(httpe))
except Exception as e:
    logging.exception('Unhandled error')
    raise HTTPException(status_code=500, detail=str(e))

---------- Health check ----------

@app.get('/health') async def health(): return {'status':'ok', 'time': import('datetime').datetime.utcnow().isoformat()}

