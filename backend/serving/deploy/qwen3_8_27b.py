"""Qwen3.8-27B (Alibaba, Apache 2.0) served by vLLM on Modal, behind an OpenAI-style chat API.

A general vision model, not an OCR model: v4a asks it to read the whole page and return the record as JSON. The weights are 55.6 GB in
bfloat16, so one H100 (80 GB) fits them with room for the KV cache of a few pages at a time. Like the other servers it is not public:
Modal's proxy requires a proxy token on every request (see docs/serving.md).

Deploy with ``modal deploy serving/deploy/qwen3_8_27b.py`` (or ``modal serve`` while iterating).
"""

import json
import subprocess

import modal

MODEL_NAME = "Qwen/Qwen3.8-27B"
MODEL_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
SERVED_MODEL_NAME = "qwen3-8-27b"  # the "model" field of a request must match this
VLLM_PORT = 8000
MINUTES = 60
CONCURRENCY = 8  # requests per container: vLLM's batch limit and Modal's scale-out threshold; 55 GB of weights leave little KV cache

image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install(
        "vllm==0.30.0"
    )  # not checked against this model: raise it if vLLM does not know the qwen3_5 architecture
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)
app = modal.App("constat-qwen3-8-27b")


@app.server(
    image=image,
    gpu="H100",
    scaledown_window=2 * MINUTES,
    startup_timeout=20 * MINUTES,  # 55 GB to load on the first start
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    port=VLLM_PORT,
    target_concurrency=CONCURRENCY,
)
class Server:
    """One vLLM process serving Qwen3.8-27B for the life of the container."""

    @modal.enter()
    def start(self):
        cmd = [
            "vllm",
            "serve",
            MODEL_NAME,
            "--revision",
            MODEL_REVISION,
            "--served-model-name",
            SERVED_MODEL_NAME,
            "--host",
            "0.0.0.0",
            "--port",
            str(VLLM_PORT),
            "--dtype",
            "bfloat16",
            "--max-model-len",  # a page is about 6,000 image tokens, the JSON answer about 3,000 more
            "16384",
            "--max-num-seqs",
            str(CONCURRENCY),
            "--max-num-batched-tokens",  # must cover the largest image
            "8192",
            "--gpu-memory-utilization",
            "0.90",
            "--enable-prefix-caching",  # every request starts with the same long prompt
            "--mm-processor-kwargs",  # keep the page up to 6.3 megapixels, so handwriting is not shrunk
            json.dumps({"min_pixels": 3136, "max_pixels": 6291456}),
        ]
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self):
        self.process.terminate()
