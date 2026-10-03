"""Smoke test for the DeepSeek-OCR-2 server: one page, called twice (cold then warm), with the loop guard enabled.

Run from ``backend/`` with ``DEEPSEEK_OCR_2_SERVER_URL`` set in ``backend/.env``.
"""

import base64
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()
URL = os.environ["DEEPSEEK_OCR_2_SERVER_URL"]
IMAGE = "../runs/v3a-dev5/straightened/000000.jpg"  # run from backend/

# 1. wait until the server answers (the first request boots a GPU container)
started = time.time()
while True:
    try:
        if httpx.get(f"{URL}/health", timeout=60).status_code == 200:
            break
    except httpx.HTTPError:
        pass
    time.sleep(5)
print(f"ready after {time.time() - started:.0f}s")

# 2. the request: image and prompt in the OpenAI chat format, plus the loop guard settings
image = base64.b64encode(open(IMAGE, "rb").read()).decode()
body = {
    "model": "deepseek-ocr-2",  # must match --served-model-name in the deploy file
    "temperature": 0,
    "max_tokens": 4096,
    "skip_special_tokens": False,  # the model's layout tokens must reach the guard and the output
    "vllm_xargs": {  # settings of the n-gram logits processor
        "ngram_size": 30,
        "window_size": 90,
        "whitelist_token_ids": [128821, 128822],  # <td> and </td> may repeat in tables
    },
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                },
                {"type": "text", "text": "Free OCR."},
            ],
        }
    ],
}

# 3. call twice: the first may still be warming up, the second is the warm time per page
for attempt in range(2):
    started = time.time()
    r = httpx.post(f"{URL}/v1/chat/completions", json=body, timeout=900)
    r.raise_for_status()
    reply = r.json()
    text = reply["choices"][0]["message"]["content"]
    print(
        f"call {attempt + 1}: {time.time() - started:.1f}s, {len(text)} characters, "
        f"{reply['usage']['completion_tokens']} tokens, finish_reason={reply['choices'][0]['finish_reason']}"
    )

print(text[:1500])
