from dotenv import load_dotenv
load_dotenv()
import os
import json
import shutil
import sqlite3
import tempfile
import uuid
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from urllib import request as urlrequest
from urllib.error import URLError
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
import pytesseract
import cloudinary
import cloudinary.uploader

from analyzer import analyze_text, ensure_dataset, extract_text, train_and_save_model
from analyzer import extract_text_with_debug

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "ayush-ai-assistant-dev-key")
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "tiff", "webp", "pdf"}
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "app.db"))

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Configure Cloudinary once at startup.
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME, api_key=CLOUDINARY_API_KEY, api_secret=CLOUDINARY_API_SECRET
    )

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ensure_dataset()
train_and_save_model()
pytesseract.pytesseract.tesseract_cmd = os.getenv(
    "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                file_url TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                result_summary TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )


_init_db()


class User(UserMixin):
    def __init__(self, user_id: int, username: str, email: str) -> None:
        self.id = str(user_id)
        self.username = username
        self.email = email


@login_manager.user_loader
def _load_user(user_id: str):
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    with _get_db_connection() as conn:
        user_row = conn.execute("SELECT id, username, email FROM users WHERE id=?", (uid,)).fetchone()
        if not user_row:
            return None
        return User(user_row["id"], user_row["username"], user_row["email"])


def _require_cloudinary_config() -> None:
    # Debug-safe: do not print API secret values.
    print(
        "Cloudinary Config:",
        {
            "cloud_name_set": bool(CLOUDINARY_CLOUD_NAME),
            "cloud_name": CLOUDINARY_CLOUD_NAME,
            # Print only a tiny prefix (avoid leaking secrets).
            "api_key_prefix": (CLOUDINARY_API_KEY[:4] + "..." if CLOUDINARY_API_KEY else ""),
        },
    )
    if not (CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET):
        raise RuntimeError(
            "Cloudinary is not configured properly. Please set "
            "CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET."
        )


def _cloudinary_upload(file_storage, folder: str) -> str:
    """
    Upload user file to Cloudinary and return the secure URL.
    """
    _require_cloudinary_config()
    # Upload expects a path or file-like object; use temp file for reliability.
    filename = secure_filename(getattr(file_storage, "filename", "upload.bin") or "upload.bin")
    ext = os.path.splitext(filename)[1].lower() or ".bin"
    data = file_storage.read()
    file_storage.stream.seek(0)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        upload_result = cloudinary.uploader.upload(
            tmp_path,
            folder=folder,
            resource_type="auto",
            use_filename=True,
        )
        return str(upload_result.get("secure_url") or upload_result.get("url") or "")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _download_url_to_temp(file_url: str, ext: str) -> str:
    """
    Download a Cloudinary URL into a temp file for OCR.
    Returns the temp file path (caller should delete it).
    """
    tmp_path = None
    tmp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()

    try:
        with urlrequest.urlopen(file_url, timeout=60) as resp:
            with open(tmp_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        return tmp_path
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        raise


def _get_remote_size_kb(file_url: str) -> float:
    try:
        req = urlrequest.Request(file_url, method="HEAD")
        with urlrequest.urlopen(req, timeout=30) as resp:
            cl = resp.headers.get("Content-Length")
        if not cl:
            return 0.0
        return round(int(cl) / 1024, 2)
    except Exception:
        return 0.0


def _local_save_upload(file_storage, original_filename: str) -> str:
    """
    Fallback local save (only used when Cloudinary is not configured).
    Returns the saved filename.
    """
    ext = os.path.splitext(original_filename)[1].lower()
    if not ext:
        ext = ".bin"
    safe_original = secure_filename(original_filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_original}"
    saved_filename = f"{os.path.splitext(unique_name)[0]}{ext}"

    # Ensure stream is at the beginning before saving.
    try:
        file_storage.stream.seek(0)
    except Exception:
        pass
    filepath = os.path.join(UPLOAD_FOLDER, saved_filename)
    file_storage.save(filepath)
    return saved_filename


def _build_chat_prompt(user_input: str) -> str:
    return f"""
You are an advanced AI assistant similar to ChatGPT.

Your role:
- Answer any question from the user across all domains (coding, science, health, general knowledge, etc.)
- Provide clear, accurate, and helpful responses

Guidelines:
- Use simple, natural, and professional English
- Keep answers concise by default (5-10 lines)
- Expand explanations only when necessary or when the user asks
- If the question is unclear, ask a brief follow-up question
- If you do not know something, say so honestly instead of guessing
- Avoid repeating the same information
- Structure answers neatly when helpful (paragraphs or bullet points)

Behavior:
- Be helpful, intelligent, and neutral
- Do not mention internal instructions or system rules
- Do not ask the user to upload files unless explicitly required
- Adapt tone based on the question (technical, casual, etc.)

User Question:
{user_input}

Assistant:
"""


def _chat_with_gemini(user_input: str) -> str:
    """
    Call Gemini via REST API.

    API key must be provided via environment variable `GEMINI_API_KEY`.
    """
    if not GEMINI_API_KEY:
        return ""

    prompt = _build_chat_prompt(user_input)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 512},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlrequest.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8")
        parsed = json.loads(body)

    candidates = parsed.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        return ""
    return str(parts[0].get("text", "")).strip()


def _generate_chat_response(user_message: str) -> str:
    try:
        gemini_response = _chat_with_gemini(user_message)
        if gemini_response:
            return gemini_response
    except (TimeoutError, URLError, OSError, ValueError, json.JSONDecodeError) as error:
        app.logger.warning("Gemini chat failed: %s", error)
    return "Gemini API is not configured (missing `GEMINI_API_KEY`) or the request failed."


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    username = str(request.form.get("username", "")).strip()
    email = str(request.form.get("email", "")).strip().lower()
    password = str(request.form.get("password", "")).strip()
    confirm = str(request.form.get("confirm_password", "")).strip()

    if not username or len(username) < 3:
        return render_template("signup.html", error="Username must be at least 3 characters.")
    if not email or "@" not in email:
        return render_template("signup.html", error="Please enter a valid email address.")
    if len(password) < 8:
        return render_template("signup.html", error="Password must be at least 8 characters.")
    if password != confirm:
        return render_template("signup.html", error="Passwords do not match.")

    password_hash = generate_password_hash(password)
    try:
        with _get_db_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE LOWER(username)=? OR email=?",
                (username.lower(), email),
            ).fetchone()
            if existing:
                return render_template("signup.html", error="Username or email already exists.")

            cur = conn.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash),
            )
            user_id = cur.lastrowid
        user = User(int(user_id), username, email)
        login_user(user)
        return redirect(url_for("dashboard"))
    except Exception:
        return render_template("signup.html", error="Signup failed. Please try again.")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username_or_email = str(request.form.get("username_or_email", "")).strip().lower()
    password = str(request.form.get("password", "")).strip()

    if not username_or_email or not password:
        return render_template("login.html", error="Missing username/email or password.")

    with _get_db_connection() as conn:
        user_row = conn.execute(
            "SELECT id, username, email, password_hash FROM users WHERE LOWER(username)=? OR email=?",
            (username_or_email, username_or_email),
        ).fetchone()
    if not user_row or not check_password_hash(user_row["password_hash"], password):
        return render_template("login.html", error="Invalid credentials.")

    user = User(int(user_row["id"]), user_row["username"], user_row["email"])
    login_user(user)
    return redirect(url_for("dashboard"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    with _get_db_connection() as conn:
        user_row = conn.execute(
            "SELECT id, username, email FROM users WHERE id=?",
            (int(current_user.id),),
        ).fetchone()
        upload_rows = conn.execute(
            "SELECT id, filename, file_url, timestamp, result_summary FROM uploads WHERE user_id=? ORDER BY timestamp DESC LIMIT 3",
            (int(current_user.id),),
        ).fetchall()
        total_uploads = conn.execute(
            "SELECT COUNT(*) as c FROM uploads WHERE user_id=?",
            (int(current_user.id),),
        ).fetchone()["c"]

    last_uploads = []
    for row in upload_rows:
        summary = {}
        if row["result_summary"]:
            try:
                summary = json.loads(row["result_summary"])
            except Exception:
                summary = {}
        last_uploads.append(
            {
                "filename": row["filename"],
                "file_url": row["file_url"],
                "timestamp": row["timestamp"],
                "score": summary.get("score"),
                "quality": summary.get("quality"),
            }
        )

    return render_template(
        "dashboard.html",
        username=user_row["username"] if user_row else "",
        email=user_row["email"] if user_row else "",
        total_uploads=total_uploads,
        last_uploads=last_uploads,
    )


@app.route("/history", methods=["GET"])
@login_required
def history():
    with _get_db_connection() as conn:
        upload_rows = conn.execute(
            "SELECT id, filename, file_url, timestamp, result_summary FROM uploads WHERE user_id=? ORDER BY timestamp DESC",
            (int(current_user.id),),
        ).fetchall()

    uploads = []
    for row in upload_rows:
        summary = {}
        if row["result_summary"]:
            try:
                summary = json.loads(row["result_summary"])
            except Exception:
                summary = {}
        uploads.append(
            {
                "filename": row["filename"],
                "file_url": row["file_url"],
                "timestamp": row["timestamp"],
                "score": summary.get("score"),
                "quality": summary.get("quality"),
                "ml_label": summary.get("ml_label"),
            }
        )

    return render_template("history.html", uploads=uploads)


@app.route("/about")
def about():
    return render_template("about.html")

def _get_updates_data():
    return [
        {
            "title": "Yoga Improves Mental Health",
            "summary": "Studies show yoga reduces stress and improves focus.",
            "content": "Recent clinical reviews show regular yoga practice is linked to lower anxiety, enhanced mood, and improved concentration. These practices also support emotional balance and cognitive clarity.",
            "tag": "Yoga",
            "date": "April 2026",
        },
        {
            "title": "Herbal Immunity Support in AYUSH",
            "summary": "Recent research highlights turmeric and ashwagandha for immune resilience.",
            "content": "New AYUSH research emphasizes the potential of turmeric and ashwagandha in strengthening immune response. The study also explores optimal dosages for daily wellness support.",
            "tag": "Herbal",
            "date": "April 2026",
        },
        {
            "title": "Mindful Breathing for Cognitive Clarity",
            "summary": "Ayurveda-based breathing exercises are linked to better concentration.",
            "content": "A recent trial shows pranayama routines improve focus and reduce mental fatigue. Participants reported clearer thinking and better task performance after daily breathing exercises.",
            "tag": "Pranayama",
            "date": "March 2026",
        },
    ]

@app.route("/updates")
def updates():
    return render_template("updates.html")

@app.route("/api/updates")
def api_updates():
    return jsonify(_get_updates_data())

@app.route("/update/<title>")
def update_detail(title):
    updates_data = _get_updates_data()
    selected_update = next((item for item in updates_data if item["title"] == title), None)
    if selected_update is None:
        return render_template("update_detail.html", title="Update not found", content="The requested research update could not be found.")
    return render_template(
        "update_detail.html",
        title=selected_update["title"],
        content=selected_update["content"],
    )

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    file = request.files.get("file")
    if not file or file.filename == "":
        return render_template("upload.html", error="Please select an image or PDF file.")
    if not _allowed_file(file.filename):
        return render_template(
            "upload.html",
            error="Unsupported file type. Use pdf, png, jpg, jpeg, bmp, tiff, or webp.",
        )

    filename = secure_filename(file.filename)
    file_url = ""
    try:
        folder = f"ayush_hackathon/user_{int(current_user.id)}"
        file_url = _cloudinary_upload(file, folder=folder)
    except Exception as upload_error:
        app.logger.error("Cloudinary upload failed, falling back to local save: %s", upload_error)
        # Cloudinary not configured or API error -> local fallback so uploads don't break.
        try:
            saved_filename = _local_save_upload(file, original_filename=filename)
            file_url = url_for("uploaded_file", filename=saved_filename, _external=True)
        except Exception as local_error:
            return render_template(
                "upload.html",
                error=f"Upload failed. Cloudinary error: {upload_error}. Local error: {local_error}",
            )

    if not file_url:
        return render_template("upload.html", error="Upload failed: empty file URL.")

    with _get_db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO uploads (user_id, filename, file_url, result_summary) VALUES (?, ?, ?, ?)",
            (int(current_user.id), filename, file_url, None),
        )
        upload_id = cur.lastrowid

    session["upload_id"] = upload_id
    return redirect(url_for("review"))


@app.route("/review", methods=["GET"])
@login_required
def review():
    upload_id = session.get("upload_id")
    if not upload_id:
        return redirect(url_for("upload"))

    with _get_db_connection() as conn:
        upload_row = conn.execute(
            "SELECT filename, file_url FROM uploads WHERE id=? AND user_id=?",
            (int(upload_id), int(current_user.id)),
        ).fetchone()

    if not upload_row:
        session.pop("upload_id", None)
        return redirect(url_for("upload"))

    uploaded_name = upload_row["filename"]
    file_url = upload_row["file_url"]

    return render_template(
        "review.html",
        uploaded_name=uploaded_name,
        uploaded_size_kb=_get_remote_size_kb(file_url),
        file_url=file_url,
        is_pdf=uploaded_name.lower().endswith(".pdf"),
    )


@app.route("/results", methods=["GET"])
@login_required
def results():
    result_data = session.get("analysis_result")
    if not result_data:
        return redirect(url_for("review"))
    return render_template("result.html", **result_data)


@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    upload_id = session.get("upload_id")
    if not upload_id:
        return jsonify({"error": "No uploaded file found. Please upload a file first."}), 400

    with _get_db_connection() as conn:
        upload_row = conn.execute(
            "SELECT id, filename, file_url FROM uploads WHERE id=? AND user_id=?",
            (int(upload_id), int(current_user.id)),
        ).fetchone()

    if not upload_row:
        session.pop("upload_id", None)
        return jsonify({"error": "Uploaded file not found. Please upload again."}), 400

    uploaded_name = upload_row["filename"]
    file_url = upload_row["file_url"]
    ext = os.path.splitext(uploaded_name)[1].lower()
    suffix = ext if ext else ".bin"

    payload = request.get_json(silent=True) or {}
    analyze_scope = str(payload.get("analyze_scope", "full_document")).strip() or "full_document"
    current_page = str(payload.get("current_page", "")).strip()
    selected_region = str(payload.get("selected_region", "")).strip()
    debug_test_mode = bool(payload.get("debug_test_mode", False))

    if current_page and "page:" not in selected_region.lower():
        selected_region = f"{selected_region}, page:{current_page}".strip(", ")

    app.logger.info("Analyze request received file=%s scope=%s", uploaded_name, analyze_scope)

    if debug_test_mode:
        app.logger.info("Debug test mode enabled for analyze endpoint")
        return jsonify(
            {
                "status": "success",
                "text": "TEST SUCCESS",
                "message": "",
                "logs": ["Debug test mode response emitted."],
            }
        )

    try:
        tmp_path = _download_url_to_temp(file_url, ext=suffix)
        file_size_kb = round(os.path.getsize(tmp_path) / 1024, 2)
        try:
            ocr_result = extract_text_with_debug(
                tmp_path, analyze_scope=analyze_scope, selected_region=selected_region
            )
            text = str(ocr_result.get("text", "")).strip()
            ocr_message = str(ocr_result.get("message", "")).strip()

            if ocr_result.get("status") != "success":
                app.logger.warning(
                    "OCR weak/failed for file=%s error=%s",
                    uploaded_name,
                    ocr_message or "Unknown OCR issue",
                )

            result = analyze_text(text)
            if not text:
                result["issues"] = ["No text extracted from image due to irrelevance."]
            elif ocr_message:
                result["issues"] = list(result.get("issues", []))
                result["issues"].append(f"OCR note: {ocr_message}")

            dataset_preview = str(result.get("dataset_relevant_text", "")).strip()
            if not dataset_preview:
                dataset_preview = text[:1200] if text else "No text extracted from image due to irrelevance."
        finally:
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass

        ai_insight = (
            "Document appears structurally consistent with mostly reliable educational phrasing."
            if result["score"] >= 75
            else "Document has mixed reliability. Review highlighted issues before accepting the content."
            if result["score"] >= 50
            else "Document shows high-risk authenticity patterns. Manual review is strongly recommended."
        )
        app.logger.info("Analyze completed file=%s score=%s", uploaded_name, result["score"])
        response_payload = {
            "status": "success",
            "text": text,
            "message": ocr_message,
            "logs": ocr_result.get("logs", []),
            "score": result["score"],
            "quality": result["quality"],
            "issues": result["issues"],
            "text_preview": dataset_preview[:1200],
            "dataset_relevant_text": dataset_preview,
            "ml_label": result["ml_label"],
            "ml_confidence": result["ml_confidence"],
            "analyze_scope": analyze_scope,
            "selected_region": selected_region,
            "uploaded_name": uploaded_name,
            "uploaded_size_kb": file_size_kb,
            "ai_insight": ai_insight,
            "redirect_url": url_for("results"),
        }
        session["analysis_result"] = response_payload.copy()

        # Persist a summary for the user's history.
        result_summary = json.dumps(
            {
                "score": result["score"],
                "quality": result["quality"],
                "ml_label": result["ml_label"],
                "ml_confidence": result["ml_confidence"],
                "issues": result["issues"],
                "text_preview": dataset_preview[:1200],
                "analyze_scope": analyze_scope,
                "selected_region": selected_region,
            }
        )
        with _get_db_connection() as conn:
            conn.execute(
                "UPDATE uploads SET result_summary=? WHERE id=? AND user_id=?",
                (result_summary, int(upload_id), int(current_user.id)),
            )
            conn.commit()

        return jsonify(response_payload)
    except Exception as error:
        app.logger.exception("Analyze endpoint crashed: %s", error)
        return jsonify(
            {
                "status": "error",
                "message": str(error),
                "text": "",
                "logs": ["Analyze endpoint exception raised."],
            }
        ), 500


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/legacy-upload", methods=["POST"])
@login_required
def legacy_upload():
    """Backward-compatible handler for older form posts."""
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            return render_template("upload.html", error="Please select an image file.")
        if not _allowed_file(file.filename):
            return render_template(
                "upload.html",
                error="Unsupported file type. Use png, jpg, jpeg, bmp, tiff, or webp.",
            )

        filename = secure_filename(file.filename)

        analyze_scope = request.form.get("analyze_scope", "full_document")
        current_page = request.form.get("current_page", "").strip()
        selected_region = request.form.get("selected_region", "").strip()
        if current_page and "page:" not in selected_region.lower():
            selected_region = f"{selected_region}, page:{current_page}".strip(", ")

        # Upload to Cloudinary and keep only the returned URL.
        folder = f"ayush_hackathon/user_{int(current_user.id)}"
        try:
            file_url = _cloudinary_upload(file, folder=folder)
        except Exception as upload_error:
            app.logger.error("Cloudinary upload failed, falling back to local save: %s", upload_error)
            try:
                saved_filename = _local_save_upload(file, original_filename=filename)
                file_url = url_for("uploaded_file", filename=saved_filename, _external=True)
            except Exception as local_error:
                return render_template(
                    "upload.html",
                    error=f"Upload failed. Cloudinary error: {upload_error}. Local error: {local_error}",
                )
        if not file_url:
            return render_template("upload.html", error="Upload failed: empty file URL.")

        with _get_db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO uploads (user_id, filename, file_url, result_summary) VALUES (?, ?, ?, ?)",
                (int(current_user.id), filename, file_url, None),
            )
            upload_id = cur.lastrowid
            session["upload_id"] = upload_id

        ext = os.path.splitext(filename)[1].lower() or ".bin"
        tmp_path = None
        text = ""
        file_size_kb = 0.0
        try:
            tmp_path = _download_url_to_temp(file_url, ext=ext)
            file_size_kb = round(os.path.getsize(tmp_path) / 1024, 2)
            text = extract_text(
                tmp_path, analyze_scope=analyze_scope, selected_region=selected_region
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        result = analyze_text(text)
        dataset_preview = str(result.get("dataset_relevant_text", "")).strip()
        if not dataset_preview:
            dataset_preview = text[:1200] if text else "No text extracted from image due to irrelevance."
        ai_insight = (
            "Document appears structurally consistent with mostly reliable educational phrasing."
            if result["score"] >= 75
            else "Document has mixed reliability. Review highlighted issues before accepting the content."
            if result["score"] >= 50
            else "Document shows high-risk authenticity patterns. Manual review is strongly recommended."
        )

        return render_template(
            "result.html",
            score=result["score"],
            quality=result["quality"],
            issues=result["issues"],
            text_preview=dataset_preview[:1200],
            ml_label=result["ml_label"],
            ml_confidence=result["ml_confidence"],
            analyze_scope=analyze_scope,
            selected_region=selected_region,
            uploaded_name=filename,
            uploaded_size_kb=file_size_kb,
            ai_insight=ai_insight,
        )

        # Persist result summary (best effort).
        try:
            result_summary = json.dumps(
                {
                    "score": result["score"],
                    "quality": result["quality"],
                    "ml_label": result["ml_label"],
                    "ml_confidence": result["ml_confidence"],
                    "issues": result["issues"],
                    "text_preview": dataset_preview[:1200],
                    "analyze_scope": analyze_scope,
                    "selected_region": selected_region,
                }
            )
            with _get_db_connection() as conn:
                conn.execute(
                    "UPDATE uploads SET result_summary=? WHERE id=? AND user_id=?",
                    (result_summary, int(upload_id), int(current_user.id)),
                )
                conn.commit()
        except Exception:
            pass

    return render_template("upload.html")

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    response = ""
    user_input = ""
    if request.method == "POST":
        user_input = request.form.get("query", "")
        response = _generate_chat_response(user_input)

    return render_template("chatbot.html", response=response, user_input=user_input)


@app.route("/chat_api", methods=["POST"])
def chat_api():
    payload = request.get_json(silent=True) or {}
    user_message = str(payload.get("message", "")).strip()
    if not user_message:
        return jsonify({"error": "Message is required."}), 400
    return jsonify({"response": _generate_chat_response(user_message)})

if __name__ == "__main__":
    app.run(debug=True)
