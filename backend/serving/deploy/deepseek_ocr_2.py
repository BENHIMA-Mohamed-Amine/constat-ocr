"""DeepSeek-OCR-2 served by vLLM on Modal, behind an OpenAI-style chat API.

The model needs vLLM's n-gram logits processor, which blocks repeated token sequences. Without it the model can get
stuck repeating a line until it runs out of tokens.

Deploy with ``modal deploy serving/deploy/deepseek_ocr_2.py`` (or ``modal serve`` while iterating).
"""

import subprocess

import modal

MODEL_NAME = "deepseek-ai/DeepSeek-OCR-2"
MODEL_REVISION = "aaa02f3811945a91062062994c5c4a3f4c0af2b0"
SERVED_MODEL_NAME = "deepseek-ocr-2"  # the "model" field of a request must match this
VLLM_PORT = 8000
MINUTES = 60
CONCURRENCY = 30  # requests per container: both vLLM's batch limit and Modal's scale-out threshold

image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.30.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1", "TRITON_ALLOW_NON_CONSTEXPR_GLOBALS": "1"})
)

hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)
app = modal.App("constat-deepseek-ocr-2")


@app.server(
    image=image,
    gpu="L4",
    scaledown_window=2 * MINUTES,
    startup_timeout=10 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    port=VLLM_PORT,
    target_concurrency=CONCURRENCY,
)
class Server:
    """One vLLM process serving DeepSeek-OCR-2 for the life of the container."""

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
            "--logits_processors",  # the loop guard, see the module docstring
            "vllm.model_executor.models.deepseek_ocr:NGramPerReqLogitsProcessor",
            "--no-enable-prefix-caching",  # every OCR page is different, so reuse never hits
            "--mm-processor-cache-gb",  # same for images
            "0",
            "--max-num-seqs",  # most requests vLLM batches together
            str(CONCURRENCY),
            "--max-num-batched-tokens",  # a page image is thousands of tokens
            "16384",
            "--max-model-len",
            "8192",
        ]
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self):
        self.process.terminate()
