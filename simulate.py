import json
import random
import time

path = "../processed_data/results.json"

while True:

    with open(path, "r") as f:
        data = json.load(f)

    for campus in data:
        for t in ["morning","afternoon","evening"]:
            change = random.randint(-2, 2)
            data[campus][t] = max(0, data[campus][t] + change)

    with open(path, "w") as f:
        json.dump(data, f, indent=4)

    print("Updated data...")

    time.sleep(5)