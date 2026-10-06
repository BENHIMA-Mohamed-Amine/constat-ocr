"""Smoke test for the Qwen3.8-27B server: auth check, then one page called twice (cold then warm).

The model is asked to read the page and answer in JSON. The full answer is saved to ``_local/`` (git-ignored) and the first part is
printed. Thinking is switched off so the answer is the JSON and nothing else.

Run from ``backend/`` with ``QWEN3_8_27B_SERVER_URL``, ``MODAL_PROXY_TOKEN_ID`` and ``MODAL_PROXY_TOKEN_SECRET`` set in
``backend/.env``. The server requires a Modal proxy token, sent as a Bearer header.
"""

import base64
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()
URL = os.environ["QWEN3_8_27B_SERVER_URL"]
TOKEN = f"{os.environ['MODAL_PROXY_TOKEN_ID']}.{os.environ['MODAL_PROXY_TOKEN_SECRET']}"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
IMAGE = "../runs/v3a-dev5/straightened/000000.jpg"  # run from backend/
OUTPUT = "../_local/qwen3_8_27b_000000.json"

PROMPT = """
This is a photographed Moroccan "constat amiable" (two-driver accident report), filled in by hand in French, with Arabic labels.
Read it and answer with one JSON object and nothing else. Use these keys: "header" (date, time, place, phone numbers), "vehicle_a" and
"vehicle_b" (make, model, plate, insurer, policy number, attestation number, validity dates, driver name, licence number). Copy what is
written, do not correct it. Use null for a value you cannot read.
""".strip()

# 1. the server must refuse a request with no token (Modal's proxy answers 401 before any GPU container starts)
print(
    f"without a token: {httpx.get(f'{URL}/health', timeout=60).status_code} (expected 401)"
)

# 2. wait until the server answers (the first request boots a GPU container and loads 55 GB)
started = time.time()
while True:
    try:
        health = httpx.get(f"{URL}/health", headers=HEADERS, timeout=60)
        if health.status_code == 200:
            break
        print(f"  waiting: {health.status_code} {health.text[:200]}")
    except httpx.HTTPError as error:
        print(f"  waiting: {error!r}")
    time.sleep(5)
print(f"ready after {time.time() - started:.0f}s")

# 3. the request: image and prompt in the OpenAI chat format
image = base64.b64encode(open(IMAGE, "rb").read()).decode()
body = {
    "model": "qwen3-8-27b",  # must match --served-model-name in the deploy file
    "temperature": 0,
    "max_tokens": 4000,
    "response_format": {"type": "json_object"},
    "chat_template_kwargs": {"enable_thinking": False},
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                },
                {"type": "text", "text": PROMPT},
            ],
        }
    ],
}

# 4. call twice: the first may still be warming up, the second is the warm time per page
for attempt in range(2):
    started = time.time()
    r = httpx.post(
        f"{URL}/v1/chat/completions", headers=HEADERS, json=body, timeout=1800
    )
    r.raise_for_status()
    reply = r.json()
    text = reply["choices"][0]["message"]["content"]
    print(
        f"call {attempt + 1}: {time.time() - started:.1f}s, {len(text)} characters, "
        f"{reply['usage']['completion_tokens']} tokens, finish_reason={reply['choices'][0]['finish_reason']}, "
        f"prompt tokens={reply['usage']['prompt_tokens']}"
    )

open(OUTPUT, "w").write(text)
print(f"saved to {OUTPUT}")
print(text[:1500])
