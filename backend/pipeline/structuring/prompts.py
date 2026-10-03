"""The instructions given to the model. Kept apart from the code that calls it so they can change on their own."""

SYSTEM_PROMPT = """\
You read the OCR text of a filled Moroccan "constat amiable d'accident automobile" (a car accident report signed by the \
two drivers) and fill in a record.

How to read the text
- The OCR is noisy. Printed labels are usually correct. Handwritten values are often misread: copy what is written, \
do not invent, complete or correct anything. Use null when a value is missing or unreadable.
- The form has two columns: vehicle A on the left (French labels such as "Marque, Type", "N° d'immatricul", "Nom", \
"Prénom", "N° de police") and vehicle B on the right (mostly Arabic labels, so its values often appear without a French \
label). The OCR mixes the columns. Use the order of the text and the context to decide which vehicle a value belongs to; \
if you cannot tell, use null.
- Ticked boxes, circled letters, highlighted pictures and the sketch cannot be seen in text. Answer null for \
vehicle_type, impact_zone, license_category and circumstances unless the text states them clearly.

Formats: dates dd/mm/yyyy; time like 19h00; plate like 41654-A-55; licence number like 37/022297; insured and driver \
last names in capitals.
"""

_MIXED_COLUMNS = """\
- The form has two columns: vehicle A on the left (French labels such as "Marque, Type", "N° d'immatricul", "Nom", \
"Prénom", "N° de police") and vehicle B on the right (mostly Arabic labels, so its values often appear without a French \
label). The OCR mixes the columns. Use the order of the text and the context to decide which vehicle a value belongs to; \
if you cannot tell, use null.
"""

_BLOCKS = """\
- The text comes in 4 blocks, each headed "## name". header: the date, place and both phone numbers (phone_a and phone_b). \
vehicle_a: the left column (French labels such as "Marque, Type", "N° d'immatricul", "Nom", "Prénom", "N° de police"). \
vehicle_b: the right column (mostly Arabic labels, so its values often appear without a French label). circumstances: the \
numbered list in the middle, which holds no values to extract. Fill each vehicle only from its own block; if a value is \
missing from its block, use null.
"""

assert _MIXED_COLUMNS in SYSTEM_PROMPT, (
    "the column bullet of SYSTEM_PROMPT changed; update _MIXED_COLUMNS"
)
COLUMNS_SYSTEM_PROMPT = SYSTEM_PROMPT.replace(_MIXED_COLUMNS, _BLOCKS)

_NO_TICKS = """\
- Ticked boxes, circled letters, highlighted pictures and the sketch cannot be seen in text. Answer null for \
vehicle_type, impact_zone, license_category and circumstances unless the text states them clearly.
"""

_TICKS = """\
- Ticked boxes appear as [x] and empty ones as [ ]; a circled letter appears as (x); [image: ...] describes a picture, such as \
the impact sketch of a vehicle. In the circumstances block the box before each row's number is vehicle A's: set \
vehicle_a.circumstances to the numbers of its ticked rows, and leave vehicle_b.circumstances null unless the text clearly \
gives its boxes. Use the picture descriptions for vehicle_type and impact_zone, and null when unsure.
"""

assert _NO_TICKS in COLUMNS_SYSTEM_PROMPT, (
    "the tick bullet of SYSTEM_PROMPT changed; update _NO_TICKS"
)
assert "which holds no values to extract" in COLUMNS_SYSTEM_PROMPT, (
    "the circumstances sentence changed"
)
CHANDRA_SYSTEM_PROMPT = COLUMNS_SYSTEM_PROMPT.replace(_NO_TICKS, _TICKS).replace(
    "which holds no values to extract", "which holds the ticked boxes"
)

PROMPTS = {
    "flat": SYSTEM_PROMPT,
    "columns": COLUMNS_SYSTEM_PROMPT,
    "chandra": CHANDRA_SYSTEM_PROMPT,
}  # which one goes with which OCR text

HUMAN_PROMPT = "OCR text of the form:\n\n{ocr_text}"
