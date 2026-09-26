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

HUMAN_PROMPT = "OCR text of the form:\n\n{ocr_text}"
