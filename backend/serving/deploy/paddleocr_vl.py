"""PaddleOCR-VL-1.6 served by vLLM on Modal, behind an OpenAI-style chat API.

Tried on the handwritten constat and dropped: given the whole page, the model reads the header and then repeats a line until the token
cap (see docs/results-log.md). Kept as a record of the setup.

Deploy with ``modal deploy serving/deploy/paddleocr_vl.py`` (or ``modal serve`` while iterating).
"""

import subprocess

import modal

MODEL_NAME = "PaddlePaddle/PaddleOCR-VL-1.6"
MODEL_REVISION = "c5630abae1d940eafe0697512a0325494b02ab42"
VLLM_PORT = 8000
MINUTES = 60

image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.30.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)


hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)
app = modal.App("constat-paddleocr-vl")


@app.server(
    image=image,
    gpu="L4",
    scaledown_window=2 * MINUTES,
    startup_timeout=10 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    port=VLLM_PORT,
    target_concurrency=8,
    unauthenticated=True,
)
class Server:
    """One vLLM process serving PaddleOCR-VL for the life of the container."""

    @modal.enter()
    def start(self):
        cmd = [
            "vllm",
            "serve",
            MODEL_NAME,
            "--revision",
            MODEL_REVISION,
            "--served-model-name",
            "paddleocr-vl",
            "--host",
            "0.0.0.0",
            "--port",
            str(VLLM_PORT),
            "--trust-remote-code",
            "--max-num-batched-tokens",
            "16384",
            "--no-enable-prefix-caching",  # prefix caching reuses shared prompt starts. Every OCR page is different, so it only wastes memory.
            "--mm-processor-cache-gb",
            "0",
            "--max-model-len",
            "8192",
        ]
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self):
        self.process.terminate()
