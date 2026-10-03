"""Chandra-OCR-2 (Datalab) served by vLLM on Modal, behind an OpenAI-style chat API.

The flags follow Datalab's own ``chandra_vllm`` launcher (github.com/datalab-to/chandra, ``chandra/scripts/vllm.py``):
a long context for a page's image plus its HTML answer, and no downscaling of the page below 6.3 megapixels.

Deploy with ``modal deploy serving/deploy/chandra_ocr_2.py`` (or ``modal serve`` while iterating).
"""

import json
import subprocess

import modal

MODEL_NAME = "datalab-to/chandra-ocr-2"
MODEL_REVISION = "af93b47dba1b47b6640c86ccf487ed2260ab9a09"
SERVED_MODEL_NAME = "chandra-ocr-2"  # the "model" field of a request must match this
VLLM_PORT = 8000
MINUTES = 60
CONCURRENCY = 30  # requests per container: both vLLM's batch limit and Modal's scale-out threshold

image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.30.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)
app = modal.App("constat-chandra-ocr-2")


@app.server(
    image=image,
    gpu="H100",
    scaledown_window=2 * MINUTES,
    startup_timeout=15 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    port=VLLM_PORT,
    target_concurrency=CONCURRENCY,
)
class Server:
    """One vLLM process serving Chandra-OCR-2 for the life of the container."""

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
            "--max-model-len",  # a page is about 4,000 image tokens, and the HTML answer can be 12,000 more
            "18000",
            "--max-num-seqs",  # most requests vLLM batches together
            str(CONCURRENCY),
            "--max-num-batched-tokens",  # must cover the largest image (about 6,100 tokens)
            "8192",
            "--gpu-memory-utilization",
            "0.85",
            "--enable-prefix-caching",  # unlike the other models: every request starts with the same long prompt
            "--mm-processor-kwargs",  # keep the page up to 6.3 megapixels, so handwriting is not shrunk
            json.dumps({"min_pixels": 3136, "max_pixels": 6291456}),
        ]
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self):
        self.process.terminate()
