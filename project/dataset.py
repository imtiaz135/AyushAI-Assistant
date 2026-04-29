from pdfminer.high_level import extract_text
import json
import re

files = [
    "Yoga_Beginner.pdf",
    "Dossier_1325.pdf",
    "Ayurvedic-Home-Remedies-English.pdf"
]

all_lines = []

for file in files:
    print(f"Processing {file}...")
    text = extract_text(file)

    # Clean text
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[^\w\s.,-]', '', text)

    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if len(line) > 40:
            all_lines.append({
                "text": line,
                "source": file
            })

# Limit to 2000 lines
dataset = all_lines[:2000]

# Save file
with open("ayush_dataset.json", "w") as f:
    json.dump(dataset, f, indent=2)

print("✅ Dataset created: ayush_dataset.json")