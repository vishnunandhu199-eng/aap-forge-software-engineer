import os
import json
import base64
import sqlite3
import firebase_admin
from firebase_admin import credentials
from flask import Flask, request, jsonify

app = Flask(__name__)

firebase_key_base64 = os.environ.get('FIREBASE_CREDENTIALS_BASE64')
firebase_key = base64.b64decode(firebase_key_base64).decode('utf-8')
cred = credentials.Certificate(json.loads(firebase_key))
firebase_admin.initialize_app(cred)
db = firestore.client()
print("Firebase Connected!")


def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme in ("sqlite", "sqlite3", ""):
            path = parsed.path or parsed.netloc
            if path.startswith("/") and os.name == "nt":
                def get_db_connection():
                    database_url = os.environ.get("DATABASE_URL")
                    if database_url:
                        parsed = urlparse(database_url)
        if parsed.scheme in ("sqlite", "sqlite3", ""):
            db_path = parsed.path[1:] if parsed.path.startswith('/') else parsed.path
        else:
            raise RuntimeError("Only SQLite is supported by the current database driver.")
    else:
        db_path = os.environ.get("FLASK_TASKS_DB", str(DEFAULT_DB_PATH))
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Iddi kothaga add chesam
    try:
        conn.execute('ALTER TABLE tasks ADD COLUMN user_id INTEGER')
    except sqlite3.OperationalError:
        pass

    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            name TEXT,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            is_verified INTEGER NOT NULL DEFAULT 0,
            verification_token TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    conn.close()


class User(UserMixin):
    def __init__(self, user_id, email, name=None):
        self.id = user_id
        self.email = email
        self.name = name or email
        self.username = self.name


def ensure_user_schema():
    conn = get_db_connection()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "email" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        columns.add("email")
    if "name" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN name TEXT")
        columns.add("name")
    if "username" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
        columns.add("username")
    if "password_hash" not in columns and "password" in columns:
        conn.execute("ALTER TABLE users RENAME COLUMN password TO password_hash")
        columns.discard("password")
        columns.add("password_hash")
    if "password_hash" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")
        columns.add("password_hash")
    if "is_verified" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0")
        columns.add("is_verified")
    if "verification_token" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN verification_token TEXT")
        columns.add("verification_token")
    if "email_verified" in columns and "is_verified" in columns:
        conn.execute("UPDATE users SET is_verified = email_verified WHERE is_verified = 0")
    conn.execute("UPDATE users SET name = COALESCE(name, username) WHERE name IS NULL")
    conn.execute("UPDATE users SET username = COALESCE(username, email) WHERE username IS NULL")
    conn.commit()
    conn.close()


def generate_verification_token(secret_key, email):
    serializer = URLSafeTimedSerializer(secret_key, salt="verify-email")
    return serializer.dumps(email)


def verify_token(secret_key, token, max_age=172800):
    serializer = URLSafeTimedSerializer(secret_key, salt="verify-email")
    try:
        return serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def send_verification_email(recipient_name, recipient_email, verify_url):
    resend_api_key = os.environ.get("RESEND_API_KEY")
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    from_address = os.environ.get("EMAIL_FROM_ADDRESS", "hello@appforge.com")
    from_name = os.environ.get("EMAIL_FROM_NAME", "App Forge")

    if not from_address:
        raise RuntimeError("Missing sender address")

    subject = "Welcome to App Forge - Verify your email"
    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <title>{subject}</title>
        <style>
          body {{ margin: 0; padding: 0; background: #071024; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
          .wrapper {{ width: 100%; padding: 32px 16px; }}
          .card {{ max-width: 580px; margin: 0 auto; background: #0e2147; border-radius: 28px; padding: 34px; box-shadow: 0 40px 90px rgba(0, 0, 0, 0.28); border: 1px solid rgba(148, 163, 184, 0.08); }}
          .brand {{ color: #7dd3fc; letter-spacing: 0.24em; text-transform: uppercase; font-size: 0.9rem; margin-bottom: 24px; }}
          h1 {{ font-size: 28px; margin: 0 0 18px; color: #ffffff; }}
          p {{ font-size: 16px; line-height: 1.8; color: #cbd5e1; margin: 0 0 24px; }}
          .button {{ display: inline-block; background: #2563eb; color: #ffffff; text-decoration: none; padding: 14px 22px; border-radius: 14px; font-weight: 700; }}
          .footer {{ margin-top: 28px; font-size: 14px; color: #94a3b8; }}
        </style>
      </head>
      <body>
        <div class="wrapper">
          <div class="card">
            <div class="brand">App Forge</div>
            <h1>Hi {recipient_name},</h1>
            <p>Thanks for joining App Forge. Click the button below to verify your email and access your new workspace.</p>
            <a href="{verify_url}" class="button">Verify Email</a>
            <p class="footer">If you didn't create this account, you can safely ignore this message.</p>
          </div>
        </div>
      </body>
    </html>
    """

    if resend_api_key:
        payload = {
            "from": f"{from_name} <{from_address}>",
            "to": [recipient_email],
            "subject": subject,
            "html": html_body,
        }
        headers = {
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        return

    if sendgrid_api_key:
        payload = {
            "personalizations": [{"to": [{"email": recipient_email}]}],
            "from": {"email": from_address, "name": from_name},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_body}],
        }
        headers = {
            "Authorization": f"Bearer {sendgrid_api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        return

    raise RuntimeError("Missing email service configuration")


socketio = SocketIO(cors_allowed_origins="*")


def create_app():
    static_dir = BASE_DIR / "python" / "static"
    if not static_dir.exists():
        static_dir = BASE_DIR / "static"

    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(static_dir))
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    socketio.init_app(app)
    init_db()
    ensure_user_schema()

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        conn = get_db_connection()
        user = conn.execute("SELECT id, email, name FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if user:
            return User(user["id"], user["email"], user["name"])
        return None

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        success = False
        success_message = None
        error = None
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            name = (request.form.get("name") or email.split("@", 1)[0]).strip()
            password = request.form.get("password") or ""
            if not name or not email or not password:
                error = "Please enter your name, email, and password."
            elif "@" not in email or "." not in email:
                error = "Please enter a valid email address."
            elif len(password) < 8:
                error = "Password must be at least 8 characters."
            else:
                conn = get_db_connection()
                existing = conn.execute("SELECT id, is_verified FROM users WHERE email = ?", (email,)).fetchone()
                if existing and existing["is_verified"]:
                    conn.close()
                    error = "This email is already registered."
                elif existing:
                    conn.close()
                    error = "This email is already registered. If you did not receive a verification email, resend it from the login page."
                else:
                    hashed_password = generate_password_hash(password)
                    token = generate_verification_token(app.secret_key, email)
                    conn.execute(
                        "INSERT INTO users (email, name, username, password_hash, is_verified, verification_token) VALUES (?, ?, ?, ?, 0, ?)",
                        (email, name, email, hashed_password, token),
                    )
                    conn.commit()
                    conn.close()

                    verify_url = url_for("verify_email", token=token, _external=True)
                    try:
                        send_verification_email(name, email, verify_url)
                        success = True
                        success_message = "Account created! Check your inbox to verify."
                    except Exception:
                        error = "Something went wrong. Please try again in a moment."
        return render_template("register.html", success=success, success_message=success_message, error=error)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            conn = get_db_connection()
            user = conn.execute("SELECT id, email, name, password_hash, is_verified FROM users WHERE email = ? OR username = ?", (email, email)).fetchone()
            conn.close()
            if not user or not check_password_hash(user["password_hash"], password):
                error = "Invalid email or password."
            # elif not user["is_verified"]:
            #   error = "Please verify your email before signing in."
            else:
                login_user(User(user["id"], user["email"], user["name"]))
                return redirect(url_for("dashboard"))
        return render_template("login.html", error=error)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.route("/resend-verification", methods=["GET", "POST"])
    def resend_verification():
        success = False
        success_message = None
        error = None
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            if not email:
                error = "Please enter your email address."
            else:
                conn = get_db_connection()
                user = conn.execute("SELECT id, name, is_verified FROM users WHERE email = ?", (email,)).fetchone()
                if not user:
                    error = "We couldn't find an account with that email."
                elif user["is_verified"]:
                    error = "This account is already verified. Please sign in."
                else:
                    token = generate_verification_token(app.secret_key, email)
                    conn.execute("UPDATE users SET verification_token = ? WHERE id = ?", (token, user["id"]))
                    conn.commit()
                    conn.close()
                    verify_url = url_for("verify_email", token=token, _external=True)
                    try:
                        send_verification_email(user["name"], email, verify_url)
                        success = True
                        success_message = "Verification email resent. Check your inbox."
                    except Exception:
                        error = "Something went wrong. Please try again in a moment."
                    return render_template("resend_verification.html", success=success, success_message=success_message, error=error)
                conn.close()
        return render_template("resend_verification.html", success=success, success_message=success_message, error=error)

    @app.route("/verify/<token>")
    def verify_email(token):
        verified_email = verify_token(app.secret_key, token)
        if not verified_email:
            return render_template("verify.html", verified=False)

        conn = get_db_connection()
        user = conn.execute("SELECT id, email, name, is_verified FROM users WHERE email = ?", (verified_email,)).fetchone()
        if not user:
            conn.close()
            return render_template("verify.html", verified=False)

        if not user["is_verified"]:
            conn.execute("UPDATE users SET is_verified = 1, verification_token = NULL WHERE id = ?", (user["id"],))
            conn.commit()
        conn.close()
        login_user(User(user["id"], verified_email, user["name"]))
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        conn = get_db_connection()
        tasks = conn.execute(
    "SELECT id, title, completed FROM tasks WHERE user_id = ? ORDER BY id",
    (current_user.id,),
    ).fetchall()
        conn.close()
        task_list = [{"id": task["id"], "title": task["title"], "completed": bool(task["completed"])} for task in tasks]
        completed_count = sum(1 for task in task_list if task["completed"])
        pending_count = len(task_list) - completed_count
        return render_template(
            "dashboard.html",
            username=current_user.name,
            tasks=task_list,
            completed_count=completed_count,
            pending_count=pending_count,
        )

    @app.route("/api/tasks", methods=["GET"])
    @login_required
    def list_tasks():
        conn = get_db_connection()
        tasks = conn.execute("SELECT id, title, completed FROM tasks WHERE user_id = ? ORDER BY id DESC", (current_user.id,)).fetchall()
        conn.close()
        return jsonify([{"id": task["id"], "title": task["title"], "completed": bool(task["completed"])} for task in tasks])

    @app.route("/api/tasks", methods=["POST"])
    @login_required
    def create_task():
        payload = request.get_json(silent=True) or {}
        title = (payload.get("title") or "").strip()
        if not title:
            return jsonify({"error": "Title is required"}), 400

        conn = get_db_connection()
        cursor = conn.execute("INSERT INTO tasks (user_id, title) VALUES (?, ?)", (current_user.id, title))
        conn.commit()
        task_id = cursor.lastrowid
        task = conn.execute("SELECT id, title, completed FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        result = {"id": task["id"], "title": task["title"], "completed": bool(task["completed"]) }
        try:
            socketio.emit('tasks_updated', {'action': 'create', 'task': result}, broadcast=True)
        except Exception:
            pass
        return jsonify(result), 201

    @app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
    @login_required
    def toggle_task(task_id):
        conn = get_db_connection()
        task = conn.execute("SELECT id, completed FROM tasks WHERE id = ? AND user_id = ?", (task_id, current_user.id)).fetchone()
        if task is None:
            conn.close()
            return jsonify({"error": "Task not found"}), 404

        new_status = 0 if task["completed"] else 1
        conn.execute("UPDATE tasks SET completed = ? WHERE id = ? AND user_id = ?", (new_status, task_id, current_user.id))
        conn.commit()
        updated_task = conn.execute("SELECT id, title, completed FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        result = {"id": updated_task["id"], "title": updated_task["title"], "completed": bool(updated_task["completed"]) }
        try:
            socketio.emit('tasks_updated', {'action': 'update', 'task': result}, broadcast=True)
        except Exception:
            pass
        return jsonify(result)

    @app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
    @login_required
    def delete_task(task_id):
        conn = get_db_connection()
        cursor = conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, current_user.id))
        conn.commit()
        conn.close()
        if cursor.rowcount == 0:
            return jsonify({"error": "Task not found"}), 404
        try:
            socketio.emit('tasks_updated', {'action': 'delete', 'task_id': task_id}, broadcast=True)
        except Exception:
            pass
        return jsonify({"message": "Task deleted"})

    return app


app = create_app()


if __name__ == "__main__":
    # Use Socket.IO runner for realtime support (eventlet recommended)
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
