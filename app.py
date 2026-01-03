from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO
import json
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"
socketio = SocketIO(app)

USERS_FILE = "users.json"
REQUESTS_FILE = "requests.json"

# ---------------- SAFE JSON LOAD ----------------
def load_json_file(filename, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
                if isinstance(default, dict) and not isinstance(data, dict):
                    return default
                if isinstance(default, list) and not isinstance(data, list):
                    return default
                return data
        except json.JSONDecodeError:
            return default
    return default

users = load_json_file(USERS_FILE, {})
requests_data = load_json_file(REQUESTS_FILE, [])

def save_users():
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def save_requests():
    with open(REQUESTS_FILE, "w") as f:
        json.dump(requests_data, f, indent=4)

# ---------------- HELPERS ----------------
def get_request_by_id(req_id):
    try:
        req_id = int(req_id)
    except ValueError:
        return None
    return next((r for r in requests_data if r["id"] == req_id), None)

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"], requests=requests_data)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users:
            return "Username already exists!"
        users[username] = {
            "password": generate_password_hash(password),
            "profile": {"bio": "", "email": ""}
        }
        save_users()
        session["user"] = username
        return redirect(url_for("index"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users and check_password_hash(users[username]["password"], password):
            session["user"] = username
            return redirect(url_for("index"))
        return "Invalid credentials!"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/post", methods=["GET", "POST"])
def post_request():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        req_id = max([r["id"] for r in requests_data], default=-1) + 1
        new_request = {
            "id": req_id,
            "title": title,
            "description": description,
            "author": session["user"],
            "solutions": []
        }
        requests_data.append(new_request)
        save_requests()
        socketio.emit("new_request", new_request)
        return redirect(url_for("index"))
    return render_template("post.html")

@app.route("/solve/<req_id>", methods=["POST"])
def solve(req_id):
    if "user" not in session:
        return redirect(url_for("login"))

    req = get_request_by_id(req_id)
    if not req:
        return "Request not found!"

    solution_text = request.form["solution"]
    solution = {"author": session["user"], "text": solution_text}
    req["solutions"].append(solution)
    save_requests()

    socketio.emit("new_solution", {"req_id": req["id"], "solution": solution})
    return redirect(url_for("index"))


@app.route("/delete/<req_id>", methods=["POST"])
def delete_request(req_id):
    if "user" not in session:
        return redirect(url_for("login"))

    req = get_request_by_id(req_id)
    if not req:
        return "Request not found!"

    # Only the author can delete their own request
    if req["author"] != session["user"]:
        return "You cannot delete this request!"

    # Remove from list
    requests_data.remove(req)
    save_requests()  # save immediately
    socketio.emit("delete_request", {"req_id": int(req_id)})
    return redirect(url_for("index"))


@app.route("/profile/<username>")
def profile(username):
    if username not in users:
        return "User not found!"
    profile_data = users[username].get("profile", {})
    user_requests = [r for r in requests_data if r["author"] == username]
    return render_template("profile.html", username=username, profile=profile_data, requests=user_requests)

# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    socketio.run(app, debug=True)
