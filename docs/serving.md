# Serving the OCR vision models

The GPU-served readers (v3c onward) run on [Modal](https://modal.com) with [vLLM](https://docs.vllm.ai), behind an OpenAI-style chat API.
The pipeline reaches them through one URL per model. Code: `backend/serving/`.

```
backend/serving/
├── deploy/    one Modal app per model: chandra_ocr_2.py, qwen3_8_27b.py, paddleocr_vl.py, deepseek_ocr_2.py
└── query/     probes you run from your machine against a deployed server (one page, called twice: cold, then warm)
```

## Models tried

| Model | App name | Served name | Result |
|---|---|---|---|
| Chandra-OCR-2 (Datalab, 5.3B) | `constat-chandra-ocr-2` | `chandra-ocr-2` | **Used by v3c.** H100 |
| Qwen3.8-27B (Alibaba, general vision model) | `constat-qwen3-8-27b` | `qwen3-8-27b` | **Used by v4a.** H100, reads the page and returns the record as JSON |
| PaddleOCR-VL-1.6 (0.9B) | `constat-paddleocr-vl` | `paddleocr-vl` | Looped on the whole handwritten page. Dropped |
| DeepSeek-OCR-2 (3.4B) | `constat-deepseek-ocr-2` | `deepseek-ocr-2` | Hallucinated after the header, even with its repetition guard. Dropped |

The evidence is in [results-log.md](results-log.md#models-that-were-tried-first-and-dropped).

## Authentication
The servers are **not public**. Modal's proxy requires a proxy token on every request and answers `401` without one, before any GPU container
starts, so nobody can run up the bill. Proxy tokens (`wk-` id, `ws-` secret) are separate from the `modal` login tokens (`ak-`, `as-`).

```bash
cd backend && uv run modal workspace proxy-tokens create --name constat-ocr    # the secret is shown once
```
```
MODAL_PROXY_TOKEN_ID=wk-...
MODAL_PROXY_TOKEN_SECRET=ws-...
```
One token pair serves every model. Clients send `Authorization: Bearer <id>.<secret>` (or `Modal-Key` and `Modal-Secret` headers). The query
scripts and `ChandraOcrEngine` read the two variables and do this. Check it:
```bash
curl -s -o /dev/null -w "%{http_code}\n" "$CHANDRA_OCR_2_SERVER_URL/health"    # 401 without the token
```
The deploy files do not set `unauthenticated=True`; Modal's default is authenticated. A request with a valid token while no container is
running gets `503` and starts one.

## One URL per model
Each model has its own variable in `backend/.env` (git ignores it), named `<MODEL>_SERVER_URL` with the model name in capitals:

```
CHANDRA_OCR_2_SERVER_URL=https://...modal.direct
PADDLEOCR_VL_SERVER_URL=
DEEPSEEK_OCR_2_SERVER_URL=
```

No trailing slash and no `/v1`; the code adds `/health` and `/v1/chat/completions`. The same rule links the registry name of an OCR engine
in the pipeline (`chandra-ocr-2`) to its variable (`CHANDRA_OCR_2_SERVER_URL`).

## Deploy, query, stop
```bash
cd backend
uv run modal deploy serving/deploy/chandra_ocr_2.py          # a permanent app; prints the URL
uv run python serving/query/chandra_ocr_2.py                 # the first call boots a GPU container (minutes)
uv run modal app logs constat-chandra-ocr-2 -f               # the container's logs, once it is running
uv run modal app stop constat-chandra-ocr-2
```

- **`modal serve` instead of `deploy`** gives a temporary dev app with a new URL each run that stops with Ctrl-C. Use it while editing a
  deploy file.
- **The app scales to zero.** After `scaledown_window` (2 minutes) with no request the GPU container stops and billing stops. The next request
  is a cold start. A stopped container that has been used before starts faster, because the weights and the compile cache are in Modal Volumes.
- **Stop apps you are not using.** They cost nothing while idle, but a deployed app is still a live endpoint (protected by the proxy token).

## Settings that matter, and why
| Setting | Why |
|---|---|
| `--revision` pinned | A model repo can change under you. The run could no longer be reproduced |
| `vllm==0.30.0` pinned | The same, for the engine |
| Volumes for `~/.cache/huggingface` and `~/.cache/vllm` | The weights download and the `torch.compile` step (about 40 s) happen once, not at every cold start |
| `--max-model-len` | The longest prompt plus answer. A page image is about 4,000 tokens, Chandra's HTML answer up to 12,000 more |
| `--max-num-seqs` and `target_concurrency` | How many requests vLLM batches, and when Modal adds a container. Both come from one constant per file |
| `--max-num-batched-tokens` | Must cover the largest image (Chandra: about 6,100 tokens) |
| `--no-enable-prefix-caching`, `--mm-processor-cache-gb 0` | For PaddleOCR-VL and DeepSeek-OCR: every page is different, so reuse never hits. Chandra turns prefix caching **on**, since every request starts with the same long prompt |
| `--mm-processor-kwargs` (Chandra) | Keeps a page up to 6.3 megapixels, so handwriting is not shrunk |
| `TRITON_ALLOW_NON_CONSTEXPR_GLOBALS=1` (DeepSeek-OCR-2) | vLLM 0.30.0's image encoder kernel for this model reads a plain Python constant that the Triton version it installs rejects. The variable is Triton's own workaround |

## What was learned
- **Speed is memory bandwidth.** Generating a token reads all the weights, so tokens per second is about memory bandwidth divided by weight
  size. L4: 300 GB/s over 10.6 GB predicts 28 tokens per second, and 27.7 was measured. H100: 221 tokens per second measured, 8 times more.
  Batching many requests shares each read of the weights, which is why concurrency raises total output but not the time of one page.
- **Memory is not the limit on these models.** The KV cache logged for PaddleOCR-VL on an L4 was about one million tokens, so around 200 pages
  at once. Compute and the request rate limit come first.
- **Output is not reproducible across GPUs.** The same page, prompt and temperature 0 finished on an L4 and looped on an H100. One run proves little.
- **Loops are a known failure of these readers.** Chandra's client regenerates an answer that ends in a repeated pattern at a higher
  temperature, and `ChandraOcrEngine` does the same. DeepSeek-OCR ships its own repetition guard (an n-gram logits processor).
- **Cold starts:** 190 to 470 s on first use, from container start, weight download, `torch.compile` and CUDA graph capture.

## Not done yet
- **Throughput test:** send 1, 4, 8, 16 and 32 pages at once and choose `--max-num-seqs` and `target_concurrency` where pages per minute stops
  rising.
- **Cost per page** (GPU seconds).
- **Self-hosting the structuring LLM** (`gpt-oss-120b` needs a card with about 80 GB), which would keep the OCR text off a third-party API.
