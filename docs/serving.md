# Serving the OCR vision models

The GPU-served readers (v3c onward) run on [Modal](https://modal.com) with [vLLM](https://docs.vllm.ai), behind an OpenAI-style chat API.
The pipeline reaches them through one URL per model. Code: `backend/serving/`.

```
backend/serving/
├── deploy/    one Modal app per model: chandra_ocr_2.py, paddleocr_vl.py, deepseek_ocr_2.py
└── query/     probes you run from your machine against a deployed server (one page, called twice: cold, then warm)
```

## Models tried

| Model | App name | Served name | Result |
|---|---|---|---|
| Chandra-OCR-2 (Datalab, 5.3B) | `constat-chandra-ocr-2` | `chandra-ocr-2` | **Used by v3c.** H100 |
| PaddleOCR-VL-1.6 (0.9B) | `constat-paddleocr-vl` | `paddleocr-vl` | Looped on the whole handwritten page. Dropped |
| DeepSeek-OCR-2 (3.4B) | `constat-deepseek-ocr-2` | `deepseek-ocr-2` | Hallucinated after the header, even with its repetition guard. Dropped |

The evidence is in [results-log.md](results-log.md#models-that-were-tried-first-and-dropped).

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
- **`unauthenticated=True` makes the URL public.** Anyone with the link can use the GPU while the app is deployed. Stop apps you are not using,
  and add authentication before relying on this.

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
- **Cost per page** (GPU seconds), and authenticated access.
- **Self-hosting the structuring LLM** (`gpt-oss-120b` needs a card with about 80 GB), which would keep the OCR text off a third-party API.
