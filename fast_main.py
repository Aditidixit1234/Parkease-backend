from ultralytics import YOLO
import os
import json
import time

# -------------------------------
# SET PATHS
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
OUTPUT_DIR = os.path.join(BASE_DIR, "processed_data")
JSON_PATH = os.path.join(OUTPUT_DIR, "results.json")

# -------------------------------
# LOAD MODEL
# -------------------------------
model = YOLO("yolov8n.pt")

# -------------------------------
# DETECTION + DATA COLLECTION
# -------------------------------
data = {}

for campus in os.listdir(DATASET_DIR):
    campus_path = os.path.join(DATASET_DIR, campus)

    data[campus] = {
        "morning": [],
        "afternoon": [],
        "evening": []
    }

    for t in os.listdir(campus_path):
        time_path = os.path.join(campus_path, t)

        for img in os.listdir(time_path):
            img_path = os.path.join(time_path, img)

            try:
                results = model(img_path)

                count = 0
                for r in results:
                    count += len(r.boxes)

                data[campus][t].append(count)

            except Exception as e:
                print("Error:", img_path, e)

# -------------------------------
# AVERAGE CALCULATION
# -------------------------------
avg = {}

for campus in data:
    avg[campus] = {}

    for t in data[campus]:
        values = data[campus][t]
        avg[campus][t] = sum(values) / len(values) if values else 0

# -------------------------------
# PEAK TIME
# -------------------------------
peak_time = {}

for campus in avg:
    peak_time[campus] = max(avg[campus], key=avg[campus].get)

time_mapping = {
    "morning": "8 AM – 11 AM",
    "afternoon": "11 AM – 2 PM",
    "evening": "2 PM – 6 PM"
}

# -------------------------------
# SAVE JSON
# -------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

final_data = {}

for campus in avg:
    final_data[campus] = {
        "morning": avg[campus]["morning"],
        "afternoon": avg[campus]["afternoon"],
        "evening": avg[campus]["evening"],
        "peak": time_mapping[peak_time[campus]]
    }

with open(JSON_PATH, "w") as f:
    json.dump(final_data, f, indent=4)

print("\n✅ JSON saved at:", JSON_PATH)

# -------------------------------
# CONFIG
# -------------------------------
total_slots = {
    "campus6": 120,
    "campus12": 80,
    "campus13": 100,
    "campus14": 60,
    "campus15": 90,
    "campus25": 70
}

eta = {
    "campus6": 4,
    "campus12": 6,
    "campus13": 5,
    "campus14": 10,
    "campus15": 7,
    "campus25": 8
}

# -------------------------------
# CALCULATIONS
# -------------------------------
available = {}
score = {}

for campus in avg:
    load = (
        avg[campus]["morning"] +
        avg[campus]["afternoon"] +
        avg[campus]["evening"]
    ) / 3

    available[campus] = total_slots[campus] - load
    score[campus] = available[campus] - eta[campus]

# -------------------------------
# BEST CAMPUS
# -------------------------------
best = max(score, key=score.get)

# -------------------------------
# SHOW ALL CAMPUSES
# -------------------------------
print("\n📊 ALL CAMPUS STATUS:\n")

for campus in available:
    print(f"{campus}")
    print(f"   Available Slots → {round(available[campus], 2)}")
    print(f"   ETA → {eta[campus]} minutes")
    print(f"   Peak Time → {time_mapping[peak_time[campus]]}")
    print("---------------------------")

# -------------------------------
# BEST CAMPUS OUTPUT
# -------------------------------
print("\n🚗 BEST CAMPUS RECOMMENDATION:\n")

print(f"Best Campus → {best}")
print(f"Available Slots → {round(available[best], 2)}")
print(f"ETA → {eta[best]} minutes")
print(f"Peak Time → {time_mapping[peak_time[best]]}")

# -------------------------------
# USER CHOOSES CAMPUS
# -------------------------------
print("\n🅿️ RESERVATION SYSTEM\n")

chosen = input("Enter campus to reserve (e.g. campus6): ").strip().lower()

if chosen not in available:
    print("❌ Invalid campus name")

elif available[chosen] <= 0:
    print("❌ No slots available in this campus")

else:
    print(f"\n✅ Slot reserved at {chosen}")
    print(f"Available Slots → {round(available[chosen], 2)}")
    print("Reservation valid for 10 seconds")

    for i in range(10, 0, -1):
        print(f"⏳ Expires in: {i} sec", end="\r")
        time.sleep(1)

    print("\n❌ Reservation expired")

# -------------------------------
# FINAL SUMMARY
# -------------------------------
print("\n📊 PEAK TIME RESULTS:\n")

for campus in peak_time:
    print(f"{campus} → Peak: {time_mapping[peak_time[campus]]}")