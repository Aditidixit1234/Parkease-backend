import bcrypt, json, os

users_file = "../processed_data/users.json"

if os.path.exists(users_file):
    with open(users_file) as f:
        users = json.load(f)
else:
    users = {}

new_users = [
    {"username": "student1", "password": "pass123", "role": "student", "email": "student1@gmail.com",  "phone": "+91xxxxxxxxxx"},
    {"username": "teacher1", "password": "pass123", "role": "teacher", "email": "teacher1@gmail.com",  "phone": "+91xxxxxxxxxx"},
]

for u in new_users:
    hashed = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode()
    users[u["username"]] = {
        "password": hashed,
        "role":     u["role"],
        "email":    u["email"],
        "phone":    u["phone"]
    }
    print(f"Created: {u['username']}")

with open(users_file, "w") as f:
    json.dump(users, f, indent=4)

print("Done!")