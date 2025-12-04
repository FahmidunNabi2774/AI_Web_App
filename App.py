from flask import Flask, render_template, request as req, send_file, redirect, url_for, flash, jsonify, session
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
import os
import requests
import jinja2
import pdfkit
from io import BytesIO
from datetime import datetime
import pypandoc
from werkzeug.utils import secure_filename
from pdf2docx import Converter


App = Flask(__name__)

# MySQL config for XAMPP
App.config['MYSQL_HOST'] = 'localhost'
App.config['MYSQL_USER'] = 'root'
App.config['MYSQL_PASSWORD'] = ''
App.config['MYSQL_DB'] = 'flask_ai_tools'

App.secret_key = "my_secret_key"
# ---------- Session / Security ----------
App.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # SESSION_COOKIE_SECURE=True,  # enable when using HTTPS
)
mysql = MySQL(App)
bcrypt = Bcrypt(App)

@App.context_processor
def inject_user():
    return {
        "is_logged_in": "user_id" in session,
        "full_name": session.get("full_name")
    }

@App.route("/signup", methods=["POST"])
def Signup():
    name = req.form.get('name', '').strip()
    email = req.form.get('email', '').strip()
    password = req.form.get('password', '')

    if not name or not email or not password:
        return jsonify(status="error", message="Missing fields"), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    existing_user = cur.fetchone()
    if existing_user:
        cur.close()
        return jsonify(status="exists")

    cur.execute("INSERT INTO users (name, email, password) VALUES (%s,%s,%s)",
                (name, email, hashed_password))
    mysql.connection.commit()

    # fetch inserted id
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    cur.close()

    user_id = row[0]

    # Optional: auto-login after signup
    session["user_id"] = user_id
    session["full_name"] = name
    session.permanent = True

    return jsonify(status="success", name=name)

@App.route("/login", methods=["GET", "POST"])
def Login():
    if req.method == "GET":
        # If already logged in, send home
        if "user_id" in session:
            return redirect(url_for("Index"))
        return render_template("Login_Form.html")

    # POST
    email = req.form.get("email", "").strip()
    password = req.form.get("password", "")

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, password FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    cur.close()

    if not row:
        flash("Invalid email or password.", "error")
        return render_template("Login_Form.html"), 401

    user_id, full_name, pw_hash = row[0], row[1], row[2]
    if not bcrypt.check_password_hash(pw_hash, password):
        flash("Invalid email or password.", "error")
        return render_template("Login_Form.html"), 401

    session["user_id"] = user_id
    session["full_name"] = full_name
    session.permanent = True

    return redirect(url_for("Index"))

@App.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("Index"))

# Home / Summarizer
@App.route("/", methods=["GET", "POST"])
def Index():
    if req.method == "POST":
        API_URL = "https://router.huggingface.co/hf-inference/models/sshleifer/distilbart-cnn-12-6"
        headers = {"Authorization": f"Bearer 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"}

        minL = 20
        data = req.form["data"]
        maxL = int(req.form["maxL"])

        def query(payload):
            response = requests.post(API_URL, headers=headers, json=payload)
            return response.json()

        output = query({
            "inputs": data,
            "parameters": {"min_length": minL, "max_length": maxL},
        })[0]

        summary_text = output.get("summary_text", "Error generating summary.")

        return render_template("index.html", result= summary_text, maxL=maxL)
    else:
        return render_template("index.html")

# Text Generator page and POST
@App.route("/Text_Generator", methods=["GET"])
def text_generator():
    return render_template("Text_Generator.html")

@App.route("/generate-text", methods=["POST"])
def generate_text():
    generated_text = ""
    prompt = req.form.get("prompt", "")
    if prompt:
        API_URL = "https://router.huggingface.co/hyperbolic/v1/chat/completions"
        headers = {"Authorization": "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"}

        def query(payload):
            response = requests.post(API_URL, headers=headers, json=payload)
            return response.json()

        output = query({
            "messages": [{"role": "user", "content": prompt}],
            "model": "deepseek-ai/DeepSeek-R1"
        })

        generated_text = output["choices"][0]["message"]["content"].split("</think>")[-1].strip()

    return render_template("Text_Generator.html", generated_text=generated_text, prompt=prompt)

# Cover Page Generator form page
@App.route("/Cover_Page_Generator")
def cover_page_form():
    return render_template("Cover_Page_Generator.html")

# Cover Page PDF generation
@App.route("/generate-cover", methods=["POST"])
def generate_cover():
    # Parse and format date
    raw_date = req.form.get("submissionDate")
    formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d/%m/%Y") if raw_date else ""

    context = {
        'Course_Code': req.form.get("courseCode"),
        'Course_Title': req.form.get("courseTitle"),
        'Lab_Report_No': req.form.get("labReportNo"),
        'Submission_Date': formatted_date,
        'Teacher_Name': req.form.get("teacherName"),
        'Teacher_Designation': req.form.get("teacherDesignation"),
        'Dept_Name': req.form.get("departmentName"),
        'Student_Name': req.form.get("studentName"),
        'Student_Roll': req.form.get("studentRoll"),
        'Student_Session': req.form.get("studentSession")
    }

    # Render template with Jinja2
    template_loader = jinja2.FileSystemLoader(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'templates'))
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template("Cover_Template.html")
    html_out = template.render(context)

    # Configure pdfkit
    config = pdfkit.configuration(wkhtmltopdf=r"C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe")

    pdf_bytes = pdfkit.from_string(
        html_out,
        False,
        configuration=config,
        options={'enable-local-file-access': ""}
    )

    # Return PDF as download
    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name='Cover_Page.pdf'
    )

@App.route("/Sentiment_Analysis")
def Sentiment_Analysis():
    return render_template("Sentiment_Analysis.html")


@App.route("/Analyse-Sentiment", methods=["POST"])
def Analyse_Sentiment():
    API_URL = "https://router.huggingface.co/hf-inference/models/tabularisai/multilingual-sentiment-analysis"
    headers = {"Authorization": f"Bearer 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"}

    user_text = req.form.get("text", "")
    
    def query(payload):
        response = requests.post(API_URL, headers=headers, json=payload)
        return response.json()

    output = query({"inputs": user_text})
    
    # Extract the sentiment with the highest score
    if isinstance(output, list) and len(output) > 0:
        sentiments = output[0]  # Get the first list of sentiment dictionaries
        if sentiments and isinstance(sentiments, list):
            # Find the sentiment with highest score
            highest_sentiment = max(sentiments, key=lambda x: x['score'])
            sentiment_result = highest_sentiment['label']
            # Optional: Include the confidence score
            confidence = round(highest_sentiment['score'] * 100, 2)
            sentiment_result = f"{sentiment_result} ({confidence}% confidence)"
        else:
            sentiment_result = "Could not determine sentiment."
    else:
        sentiment_result = "Could not determine sentiment."

    return render_template("Sentiment_Analysis.html", sentiment_result=sentiment_result)

#Text_to_Speech Route
@App.route("/text_to_speech")
def Text_To_Speech():
    return render_template("Text_To_Speech.html")

# PDF to DOC Route
# Route to render the upload form
@App.route("/pdf_to_doc")
def pdf_to_doc_form():
    return render_template("pdf_to_doc.html")

# Route to handle file upload and conversion
@App.route("/pdf-to-doc-convert", methods=["POST"])
def pdf_to_doc_convert():
    uploaded_file = req.files.get("pdf_file")

    if uploaded_file and uploaded_file.filename.endswith(".pdf"):
        filename = secure_filename(uploaded_file.filename)

        # Ensure 'temp' directory exists
        temp_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_dir, exist_ok=True)

        # Save uploaded PDF
        pdf_path = os.path.join(temp_dir, filename)
        uploaded_file.save(pdf_path)

        # Define output DOCX path
        docx_filename = filename.rsplit(".", 1)[0] + ".docx"
        docx_path = os.path.join(temp_dir, docx_filename)

        try:
            # Convert PDF to DOCX
            cv = Converter(pdf_path)
            cv.convert(docx_path, start=0, end=None)
            cv.close()

            return send_file(
                docx_path,
                as_attachment=True,
                download_name=docx_filename,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        except Exception as e:
            return f"Error during conversion: {str(e)}"
    else:
        return "Please upload a valid PDF file.", 400

if __name__ == "__main__":
    App.run(debug=True)
