# main.py
# ChatGPT Brain - Starter FastAPI backend
# - /chat: interact with the assistant
# - /propose-upgrade: assistant can propose a self-upgrade (draft code/skill)
# - /approve-upgrade: you approve the upgrade and it will be staged for manual deployment
# - encrypted local memory
# - safe sandbox stub (disabled by default)

import os
import json
import asyncio
import base64
import hashlib
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
from cryptography.fernet import Fernet

# ------------------ Configuration ------------------
HF_TOKEN = os.getenv('HF_TOKEN') or os.getenv('HUGGINGFACE_API_TOKEN')
MEMORY_FILE = os.getenv('MEMORY_FILE', 'assistant_memory.enc')
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')  # must be 32 url-safe base64 bytes
ALLOW_AUTO_DEPLOY = os.getenv('ALLOW_AUTO_DEPLOY', 'false').lower() == 'true'  # safety: default false

# ------------------ Minimal validation ------------------
if not ENCRYPTION_KEY:
    # generate a stable key for dev only if not provided (not for production)
    # print warning in logs; in production set ENCRYPTION_KEY in Render env.
    print('WARNING: ENCRYPTION_KEY not set. Generating temporary key (not secure for production).')
    ENCRYPTION_KEY = base64.urlsafe_b64encode(hashlib.sha256(b'default_ankit_key').digest())

fernet = Fernet(ENCRYPTION_KEY)

app = FastAPI(title='ChatGPT Brain - Starter')

# ------------------ Models ------------------
class ChatRequest(BaseModel):
    user_id: Optional[str] = 'default'
    prompt: str
    allow_learn: Optional[bool] = False  # whether assistant may add to memory

class ProposeUpgradeRequest(BaseModel):
    user_id: Optional[str] = 'default'
    prompt: str  # description of new skill to add

class ApproveUpgradeRequest(BaseModel):
    user_id: Optional[str] = 'default'
    proposal_id: str
    approve: bool

# ------------------ Helpers: memory ------------------
async def read_memory() -> Dict[str, Any]:
    try:
        if not os.path.exists(MEMORY_FILE):
            return {}
        with open(MEMORY_FILE, 'rb') as f:
            encrypted = f.read()
        data = fernet.decrypt(encrypted)
        return json.loads(data.decode())
    except Exception as e:
        print('Memory read error:', e)
        return {}

async def write_memory(data: Dict[str, Any]):
    try:
        raw = json.dumps(data, ensure_ascii=False).encode()
        encrypted = fernet.encrypt(raw)
        with open(MEMORY_FILE, 'wb') as f:
            f.write(encrypted)
    except Exception as e:
        print('Memory write error:', e)

# ------------------ Simple HF call (text generation) ------------------
async def call_hf_text(prompt: str, model: str = 'gpt2') -> str:
    if not HF_TOKEN:
        raise RuntimeError('Hugging Face token not set')
    url = f'https://api-inference.huggingface.co/models/{model}'
    headers = {'Authorization': f'Bearer {HF_TOKEN}'}
    payload = {'inputs': prompt}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        j = r.json()
        # many HF models return text in different shapes; handle common case
        if isinstance(j, dict) and 'error' in j:
            raise RuntimeError('Model error: ' + str(j['error']))
        # if list of dicts with 'generated_text'
        if isinstance(j, list) and 'generated_text' in j[0]:
            return j[0]['generated_text']
        # else fallback to string conversion
        return str(j)

# ------------------ In-memory proposal store (simple) ------------------
PROPOSALS_FILE = 'proposals.json'

def load_proposals():
    if not os.path.exists(PROPOSALS_FILE):
        return {}
    try:
        with open(PROPOSALS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_proposals(p):
    with open(PROPOSALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(p, f, ensure_ascii=False, indent=2)

# ------------------ Endpoints ------------------
@app.get('/health')
async def health():
    return {'status':'ok'}

@app.post('/chat')
async def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    """Main chat endpoint. Uses HF as the core 'brain'.
    If allow_learn True, assistant will append safe summaries to memory (only with user consent).
    """
    memory = await read_memory()
    conversation_history = memory.get('conversations', [])

    # Build prompt with memory summary (minimal)
    memory_summary = memory.get('summary') or ''
    full_prompt = f"Memory:\n{memory_summary}\n\nUser: {req.prompt}\nAssistant:"

    try:
        resp = await call_hf_text(full_prompt, model=os.getenv('HF_MODEL', 'gpt2'))
    except Exception as e:
        print("Error calling HF model:", e)
        raise HTTPException(status_code=500, detail=str(e))

    # Save conversation locally
    conversation_history.append({'prompt': req.prompt, 'response': resp})
    memory['conversations'] = conversation_history[-200:]  # keep last 200

    # Optionally learn (append short summary) ONLY if user allowed
    if req.allow_learn:
        try:
            summ = await call_hf_text('Summarize in one line: ' + req.prompt,
                                     model=os.getenv('HF_MODEL', 'gpt2'))
            mem_summary = memory.get('summary', '')
            memory['summary'] = (mem_summary.strip() + ' ' + summ.strip())[:2000]
            background_tasks.add_task(write_memory, memory)
        except Exception as e:
            print('Learning step failed:', e)

    return {'response': resp}
@app.post('/propose-upgrade')
async def propose_upgrade(req: ProposeUpgradeRequest):
    """Assistant proposes an upgrade skill (boilerplate code, description). Stored as a proposal for user approval."""
    prompt = (
        f"You are a software engineer. Draft a safe Python module that provides: {req.prompt}\n\n"
        "Include: function signature, brief docstring, example usage. "
        "Keep code minimal and safe (no network calls, no shell execution)."
    )

    try:
        code = await call_hf_text(prompt, model=os.getenv('HF_MODEL', 'gpt2'))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    proposals = load_proposals()
    pid = hashlib.sha1((req.user_id + req.prompt + code).encode()).hexdigest()[:10]
    proposals[pid] = {
        'user_id': req.user_id,
        'prompt': req.prompt,
        'code': code,
        'approved': False
    }
    save_proposals(proposals)
    return {'proposal_id': pid, 'summary': req.prompt}

@app.post('/approve-upgrade')
async def approve_upgrade(req: ApproveUpgradeRequest):
    proposals = load_proposals()
    p = proposals.get(req.proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail='Proposal not found')
    if not req.approve:
        p['approved'] = False
        save_proposals(proposals)
        return {'status':'rejected'}

    # Approve: stage the code into 'staging_skills' directory for manual review
    os.makedirs('staging_skills', exist_ok=True)
    fname = f'staging_skills/skill_{req.proposal_id}.py'
    with open(fname, 'w', encoding='utf-8') as f:
        f.write("# Auto-generated skill - review before enabling")
        f.write(p['code'])

    p['approved'] = True
    p['staged_file'] = fname
    save_proposals(proposals)

    # Auto-deploy is disabled by default for safety.
    if ALLOW_AUTO_DEPLOY:
        # In production you'd add CI/CD integration here. For safety we skip.
        pass

    return {'status':'staged', 'file': fname}

# ------------------ Safe sandbox stub (DOES NOT EXECUTE CODE) ------------------
@app.post('/run-sandbox')
async def run_sandbox(code: Dict[str,Any]):
    """This is a safe stub. It does NOT execute arbitrary code. Execution must be enabled manually and safely.
    DO NOT enable remote code execution unless you understand security implications.
    """
    return {'status':'disabled', 'note':'Sandbox execution disabled for safety. Review staging_skills manually.'}

# ------------------ Simple admin endpoints ------------------
@app.get('/proposals')
async def list_proposals():
    return load_proposals()

@app.get('/memory')
async def show_memory():
    # return a limited safe view of memory (do not leak secrets)
    mem = await read_memory()
    return {'summary': mem.get('summary',''), 'conversations_count': len(mem.get('conversations',[]))}

