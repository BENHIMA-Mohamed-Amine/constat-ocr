"""Smoke test for the Chandra-OCR-2 server: one page, called twice (cold then warm).

Chandra answers in HTML, one ``div`` per layout block, each with a ``data-bbox`` (x0 y0 x1 y1, normalised 0-1000) and a
``data-label``. The full answer is saved to ``_local/`` (git-ignored) and the first part is printed.

Run from ``backend/`` with ``CHANDRA_OCR_2_SERVER_URL`` set in ``backend/.env``.
"""

import base64
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()
URL = os.environ["CHANDRA_OCR_2_SERVER_URL"]
IMAGE = "../runs/v3a-dev5/straightened/000000.jpg"  # run from backend/
OUTPUT = "../_local/chandra_ocr_2_000000.html"

# The prompt the model was trained with, copied from github.com/datalab-to/chandra (chandra/prompts.py, "ocr_layout").
ALLOWED_TAGS = [
    "math", "br", "i", "b", "u", "del", "sup", "sub", "table", "tr", "td", "p", "th", "div", "pre", "h1", "h2", "h3",
    "h4", "h5", "ul", "ol", "li", "input", "a", "span", "img", "hr", "tbody", "small", "caption", "strong", "thead",
    "big", "code", "chem",
]  # fmt: skip
ALLOWED_ATTRIBUTES = [
    "class", "colspan", "rowspan", "display", "checked", "type", "border", "value", "style", "href", "alt", "align",
    "data-bbox", "data-label",
]  # fmt: skip

PROMPT_ENDING = f"""
Only use these tags {ALLOWED_TAGS}, and these attributes {ALLOWED_ATTRIBUTES}.

Guidelines:
* Inline math: Surround math with <math>...</math> tags. Math expressions should be rendered in KaTeX-compatible LaTeX. Use display for block math.
* Tables: Use colspan and rowspan attributes to match table structure.
* Formatting: Maintain consistent formatting with the image, including spacing, indentation, subscripts/superscripts, and special characters.
* Images: Include a description of any images in the alt attribute of an <img> tag. Do not fill out the src property. Describe in detail inside the div tag. Also convert charts to high fidelity data, and convert diagrams to mermaid.
* Forms: Mark checkboxes and radio buttons properly.
* Text: join lines together properly into paragraphs using <p>...</p> tags.  Use <br> tags for line breaks within paragraphs, but only when absolutely necessary to maintain meaning.
* Chemistry: Use <chem>...</chem> tags for chemical formulas with reactive SMILES.
* Lists: Preserve indents and proper list markers.
* Use the simplest possible HTML structure that accurately represents the content of the block.
* Make sure the text is accurate and easy for a human to read and interpret.  Reading order should be correct and natural.
""".strip()

PROMPT = f"""
OCR this image to HTML, arranged as layout blocks.  Each layout block should be a div with the data-bbox attribute representing the bounding box of the block in x0 y0 x1 y1 format.  Bboxes are normalized 0-1000. The data-label attribute is the label for the block.

Use the following labels:
- Caption
- Footnote
- Equation-Block
- List-Group
- Page-Header
- Page-Footer
- Image
- Section-Header
- Table
- Text
- Complex-Block
- Code-Block
- Form
- Table-Of-Contents
- Figure
- Chemical-Block
- Diagram
- Bibliography
- Blank-Page

{PROMPT_ENDING}
""".strip()

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

# 2. the request: image and prompt in the OpenAI chat format, with the sampling Datalab's own client uses
image = base64.b64encode(open(IMAGE, "rb").read()).decode()
body = {
    "model": "chandra-ocr-2",  # must match --served-model-name in the deploy file
    "temperature": 0,
    "top_p": 0.1,
    "max_tokens": 12000,  # Datalab's default is 12,384
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

# 3. call twice: the first may still be warming up, the second is the warm time per page
for attempt in range(2):
    started = time.time()
    r = httpx.post(f"{URL}/v1/chat/completions", json=body, timeout=1800)
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
