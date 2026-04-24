from flask import Flask, render_template, request, redirect, session, jsonify
from flask_socketio import SocketIO
import subprocess, threading, time, os, signal

app = Flask(__name__)
app.secret_key = "change_this_secret"
socketio = SocketIO(app, cors_allowed_origins="*")

USERNAME = "admin"
PASSWORD = "12345"

process = None
auto_restart = False

def login_required():
    return session.get("login") == True

def read_logs(proc):
    global process, auto_restart
    for line in iter(proc.stdout.readline, ""):
        socketio.emit("log", line)
    proc.stdout.close()

    if auto_restart:
        time.sleep(2)
        start_process()

def start_process():
    global process
    if process is None or process.poll() is not None:
        process = subprocess.Popen(
            ["python", "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        threading.Thread(target=read_logs, args=(process,), daemon=True).start()
        socketio.emit("log", "✅ Bot started\n")
        return True
    return False

@app.route("/")
def home():
    if not login_required():
        return redirect("/login")
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == USERNAME and request.form["password"] == PASSWORD:
            session["login"] = True
            return redirect("/")
        return render_template("login.html", error="Wrong username or password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/start")
def start_bot():
    if not login_required(): return jsonify({"error": "unauthorized"})
    ok = start_process()
    return jsonify({"status": "started" if ok else "already running"})

@app.route("/stop")
def stop_bot():
    global process
    if not login_required(): return jsonify({"error": "unauthorized"})

    if process and process.poll() is None:
        process.terminate()
        process = None
        socketio.emit("log", "🛑 Bot stopped\n")
        return jsonify({"status": "stopped"})
    return jsonify({"status": "not running"})

@app.route("/restart")
def restart_bot():
    global process
    if not login_required(): return jsonify({"error": "unauthorized"})

    if process and process.poll() is None:
        process.terminate()
        process = None
        time.sleep(1)

    start_process()
    return jsonify({"status": "restarted"})

@app.route("/status")
def status():
    running = process is not None and process.poll() is None
    return jsonify({
        "status": "running" if running else "stopped",
        "auto_restart": auto_restart
    })

@app.route("/auto_restart")
def toggle_auto_restart():
    global auto_restart
    if not login_required(): return jsonify({"error": "unauthorized"})
    auto_restart = not auto_restart
    return jsonify({"auto_restart": auto_restart})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
