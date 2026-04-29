import json
import csv

# Load JSON
with open("ayush_dataset.json", "r", encoding="utf-8") as f:
    json_data = json.load(f)

# Open CSV in append mode
with open("dataset.csv", "a", newline='', encoding="utf-8") as f:
    writer = csv.writer(f)

    for item in json_data:
        text = item.get("text", "")

        # Default label = 1 (valid)
        label = 1  

        writer.writerow([text, label])

print("✅ JSON data added to CSV")