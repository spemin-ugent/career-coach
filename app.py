from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from openai import OpenAI
import base64
import os

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Set secret key for session handling
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "png", "jpg", "jpeg"}

MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    session.clear()  # ✅ deletes all stored session data when page reloads
    return render_template("chat.html")

@app.route("/chat", methods=["POST"])
def chat():
    message = request.form.get("message")
    uploaded_file = request.files.get("file")

    message_parts = [{"type": "text", "text": message}]

    # Step 1️⃣ Handle new file upload (if present)
    if uploaded_file and allowed_file(uploaded_file.filename):
        filename = secure_filename(uploaded_file.filename)
        ext = filename.rsplit(".", 1)[1].lower()
        mime_type = MIME_TYPES.get(ext, "application/octet-stream")

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        uploaded_file.save(file_path)

        with open(file_path, "rb") as f:
            encoded_bytes = base64.b64encode(f.read()).decode("utf-8")
        file_data = f"data:{mime_type};base64,{encoded_bytes}"

        # ✅ Store file info in session for reuse
        session["uploaded_file_name"] = filename
        session["uploaded_file_data"] = file_data

        # Add to current message
        message_parts.append({
            "type": "file",
            "file": {"filename": filename, "file_data": file_data}
        })

    # Step 2️⃣ If no new upload, reuse previous file from session
    elif "uploaded_file_data" in session:
        message_parts.append({
            "type": "file",
            "file": {
                "filename": session["uploaded_file_name"],
                "file_data": session["uploaded_file_data"]
            }
        })

    # Step 3️⃣ Send request to OpenAI
    try:
        completion = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional career advisor that reads uploaded documents "
                        "like resumes and gives detailed, personalized guidance."
                    )
                },
                {"role": "user", "content": message_parts}
            ],
            temperature=0.7,
            max_tokens=500
        )

        ai_reply = completion.choices[0].message.content.strip()

    except Exception as e:
        ai_reply = f"⚠️ OpenAI API Error: {str(e)}"

    return jsonify({
        "user_message": message,
        "ai_reply": ai_reply,
        "using_saved_file": "uploaded_file_data" in session
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
