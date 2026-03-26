from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from database import get_connection
import os
import io
import sys
import re
import shutil
from werkzeug.utils import secure_filename
from models import analyze_resume, extract_skills
import time
from models import get_required_skills_from_db
import fitz  # PyMuPDF for PDFs
from docx import Document
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
import subprocess
import json
import tempfile
from flask import jsonify

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)


UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==============================
# FUNCTION TO READ RESUME FILE
# ==============================
def read_resume(file_path):
    """Reads a resume file and extracts text based on its format."""
    if file_path.endswith('.pdf'):
        text = ""
        try:
            with fitz.open(file_path) as pdf:
                for page in pdf:
                    text += page.get_text()
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return None
        return text

    elif file_path.endswith('.docx'):
        text = ""
        try:
            doc = Document(file_path)
            for para in doc.paragraphs:
                text += para.text + '\n'
        except Exception as e:
            print(f"Error reading DOCX: {e}")
            return None
        return text
    
    else:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='ISO-8859-1') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            return None

# ==============================
# HOME ROUTE
# ==============================
@app.route('/')
def home():
    return render_template('home.html')

# ==============================
# CANDIDATE ROUTE
# ==============================
@app.route('/candidate', methods=['GET', 'POST'])
def candidate():
    if request.method == 'POST':
        name = request.form.get('name')
        designation = request.form.get('designation')
        file = request.files.get('resume')

        if not name or not designation or not file:
            return "All fields are required", 400

        required_skills = get_required_skills_from_db(designation)
        if not required_skills:
            return render_template('designation_not_found.html', designation=designation)

        if file and file.filename:
            filename = secure_filename(f"{int(time.time())}_{file.filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            try:
                file.save(file_path)

                resume_text = read_resume(file_path)  # ✅ Use the fixed function
                if not resume_text:
                    return "Failed to read resume file", 400

                extracted_skills = extract_skills(resume_text)

                match_score, missing_skills = analyze_resume(resume_text, designation)

                session['candidate_name'] = name
                session['match_score'] = match_score
                session['designation'] = designation
                session['resume_path'] = filename

                connection = get_connection()
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO candidates (name, designation, score, resume_path, uploaded_at) 
                        VALUES (%s, %s, %s, %s, NOW())
                        """,
                        (name, designation, float(match_score), filename)
                    )
                    connection.commit()

                if match_score >= 60:
                    return render_template('aptitude_test.html')

                return render_template(
                    'low_match.html',
                    match_score=round(match_score, 2),
                    missing_skills=missing_skills
                )

            except Exception as e:
                app.logger.error(f"Error processing file: {str(e)}")
                return f"An error occurred: {str(e)}", 500

    return render_template('upload_resume.html')

# ==============================
# SERVE UPLOADED FILES
# ==============================
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded resume files."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/match_resume', methods=['POST'])
def match_resume():
    candidate_name = request.form.get('candidate_name')
    designation = request.form.get('designation')

    if not candidate_name or not designation:
        return "Invalid candidate data.", 400

    # ✅ Store candidate info in session
    session['candidate_name'] = candidate_name
    session['designation'] = designation  

    return redirect(url_for('aptitude_test'))  # Move to Aptitude Test


# ==============================
# START INTERVIEW
# ==============================
@app.route('/start_interview')
def start_interview():
    if session.get('designation'):
        return redirect(url_for('aptitude'))
    return redirect(url_for('home'))


# ==============================
# APTITUDE TEST
# ==============================
@app.route('/aptitude', methods=['GET', 'POST'])
def aptitude():
    if request.method == 'POST':
        num_questions = 5
        answers = [request.form.get(f'answers_{i}', "").strip() for i in range(num_questions)]
        
        correct_answers = ["45", "210 km", "30", "6 hours", "$80"]
        correct_answers = [ans.strip().lower() for ans in correct_answers]  # Normalize answers

        # ✅ Debugging Output
        print(f"[DEBUG] Submitted Answers: {answers}")
        print(f"[DEBUG] Expected Answers: {correct_answers}")

        # ✅ Compare answers
        score = sum(1 for i in range(num_questions) if answers[i].strip().lower() == correct_answers[i])

        print(f"[DEBUG] Aptitude Score: {score}")  # Log the score

        if score >= 3:
            return redirect(url_for('technical'))
        else:
            return render_template('fail.html', message="You did not pass the aptitude round.")

    return render_template('aptitude_test.html')




# ============================== 
# SUBMIT ANSWERS (Fixed)
# ==============================
@app.route('/submit_answers', methods=['POST'])
def submit_answers():
    try:
        candidate_name = session.get('candidate_name')
        designation = session.get('designation')

        if not candidate_name or not designation:
            return "Session expired. Please restart the test.", 400

        aptitude_score = 0
        technical_score = 0
        coding_correct = False
        responses = []
        test_type = request.form.get('test_type')

        correct_aptitude_answers = ["45", "210", "30", "6 hours", "$80"]
        correct_technical_answers = ["O(log n)", "Stack", "Structured Query Language", "Insertion Sort"]

        # ✅ Aptitude Test
        if test_type == "aptitude":
            answers = [request.form.get(f'answers_{i}', "").strip().lower() for i in range(5)]
            correct = [ans.strip().lower() for ans in correct_aptitude_answers]
            aptitude_score = sum(1 for i in range(5) if answers[i] == correct[i])
            if aptitude_score >= 3:
                return redirect(url_for('technical'))
            else:
                return render_template('fail.html', message="You failed the aptitude test.")

        # ✅ Technical Test
        elif test_type == "technical":
            answers = [request.form.get(f'q{i+1}', "").strip() for i in range(4)]
            technical_score = sum(1 for i in range(4) if answers[i] == correct_technical_answers[i])

            language = request.form.get("language")
            code_solution = request.form.get("code_solution", "").strip()

            if code_solution:
                result = evaluate_code_directly(language, code_solution)
                if result["success"]:
                    coding_correct = True
                else:
                    print("[ERROR] Code failed:", result["message"])

            if technical_score >= 3 and coding_correct:
                return redirect(url_for('hr_test'))
            else:
                return render_template('fail.html', message="You failed the technical test.")

        # ✅ HR Test
        elif test_type == "hr":
            for i in range(3):
                question = f"HR Question {i+1}"
                answer = request.form.get(f'hr_{i}', "").strip()
                if answer:
                    # Very basic scoring: 10 if >5 words, else 5
                    score = 10 if len(answer.split()) > 5 else 5
                    responses.append((candidate_name, designation, question, answer, score))

            try:
                connection = get_connection()
                with connection.cursor() as cursor:
                    sql = """
                        INSERT INTO interview_responses (candidate_name, designation, question, response, confidence_score)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    cursor.executemany(sql, responses)
                    connection.commit()
            finally:
                connection.close()

            return render_template('interview_result.html', score=(aptitude_score + technical_score))

    except Exception as e:
        app.logger.error(f"Error processing submission: {e}")
        return f"An error occurred: {e}", 500

@app.route('/run_code', methods=['POST'])
def run_code():
    try:
        data = request.get_json()
        code = data.get("code", "")
        language = data.get("language", "").lower()

        if not code or not language:
            return jsonify({"status": "error", "message": "Missing code or language."})

        if not validate_code_input(code):
            return jsonify({"status": "error", "message": "Code too long or unsafe."})

        if language == "python":
            output = run_python_code(code)
        elif language == "c":
            output = run_c_code(code)
        elif language == "java":
            output = run_java_code(code)
        else:
            return jsonify({"status": "error", "message": f"Unsupported language: {language}"})

        return jsonify({"status": "success", "output": output})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Unexpected server error: {str(e)}"})

def evaluate_code_directly(language, code_solution):
    try:
        expected_output = "120"

        if not validate_code_input(code_solution):
            return {"success": False, "message": "Invalid code."}

        if language == "python":
            output = run_python_code(code_solution)
        elif language == "c":
            output = run_c_code(code_solution)
        elif language == "java":
            output = run_java_code(code_solution)
        else:
            return {"success": False, "message": "Unsupported language"}

        return {"success": output.strip() == expected_output, "output": output}

    except Exception as e:
        return {"success": False, "message": str(e)}

def validate_code_input(code):
    return len(code) < 5000  # Simple length check to block large payloads


def run_python_code(code):
    try:
        python_exec = shutil.which("python") or shutil.which("py") or sys.executable
        process = subprocess.run([python_exec, "-c", code], capture_output=True, text=True, timeout=3)
        return process.stdout.strip() if process.returncode == 0 else f"Error: {process.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "Timeout Error"


def run_c_code(code):
    try:
        print("GCC path found:", shutil.which("gcc"))  # Add this line to confirm if Python can find gcc

        with tempfile.TemporaryDirectory() as tmpdirname:
            code_file = os.path.join(tmpdirname, "program.c")
            exe_file = os.path.join(tmpdirname, "program.exe")

            with open(code_file, "w") as f:
                f.write(code)

            # Compile the C code
            compile_result = subprocess.run(["gcc", code_file, "-o", exe_file], capture_output=True, text=True)

            if compile_result.returncode != 0:
                return f"Compilation Error: {compile_result.stderr.strip()}"

            run_result = subprocess.run([exe_file], capture_output=True, text=True, timeout=3)
            return run_result.stdout.strip() if run_result.returncode == 0 else f"Runtime Error: {run_result.stderr.strip()}"

    except subprocess.TimeoutExpired:
        return "Timeout Error"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
    
    
def run_java_code(code):
    try:
        with open("Main.java", "w") as f:

            f.write(code)

        compile_result = subprocess.run(["javac", "Main.java"], capture_output=True, text=True)
        if compile_result.returncode != 0:
            return f"Compilation Error:\n{compile_result.stderr.strip()}"

        process = subprocess.run(["java", "Main"], capture_output=True, text=True, timeout=5)
        return process.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Timeout Error"
    except Exception as e:
        return str(e)



# ==============================
# TECHNICAL ROUND
# ==============================
@app.route('/technical', methods=['GET', 'POST'])
def technical():
    if request.method == 'POST':
        num_technical_questions = 4  # ✅ 4 MCQs + 1 Coding
        correct_answers = ["O(log n)", "Stack", "Structured Query Language", "Insertion Sort"]

        # ✅ Get answers from form
        answers = [request.form.get(f'q{i+1}', "") for i in range(num_technical_questions)]
        score = sum(1 for i in range(num_technical_questions) if answers[i] == correct_answers[i])

        print(f"\n[DEBUG] Technical Score: {score}")

        # ✅ Check coding question
        language = request.form.get("language")
        code_solution = request.form.get("code_solution", "").strip()
        coding_correct = False

        if code_solution and "factorial" in code_solution and ("for" in code_solution or "while" in code_solution):
            coding_correct = True  

        # ✅ Move to HR Test if passed
        if score > 3 and coding_correct:
            return redirect(url_for('hr_test'))
        else:
            return render_template('fail.html', message="You did not pass the technical round.")

    # ✅ Store technical questions in session
    if 'technical_questions' not in session:
        session['technical_questions'] = [
            {"question": "What is the time complexity of binary search?", "options": ["O(n)", "O(log n)", "O(n^2)", "O(1)"], "correct": "O(log n)"},
            {"question": "Which data structure follows LIFO?", "options": ["Queue", "Array", "Stack", "Linked List"], "correct": "Stack"},
            {"question": "What does SQL stand for?", "options": ["Structured Query Language", "Simple Query Logic", "Sequential Query Loader", "None"], "correct": "Structured Query Language"},
            {"question": "Which sorting algorithm is in-place?", "options": ["Merge Sort", "Heap Sort", "Quick Sort", "Insertion Sort"], "correct": "Insertion Sort"}
        ]

    return render_template('technical_test.html', questions=session['technical_questions'])


# ==============================
# HR ROUND
# ==============================
# Sample HR Questions
QUESTIONS = [
    "Tell me about yourself.",
    "Why do you want to join our company?",
    "What are your strengths and weaknesses?"
]

# HR Test Page
@app.route('/hr_test')
def hr_test():
    session['question_index'] = 0
    session['hr_answers'] = []  # Reset answers at the start
    return render_template('hr_test.html')

# Get a Question for Voice Interview
@app.route('/get_question', methods=['GET'])
def get_question():
    index = session.get('question_index', 0)
    if index >= len(QUESTIONS):
        return jsonify({'done': True, 'message': "Interview complete. Thank you!"})
    return jsonify({'done': False, 'question': QUESTIONS[index]})

# Submit a Voice Answer
@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.get_json()
    answer = data.get('answer', '').strip()

    index = session.get('question_index', 0)
    hr_answers = session.get('hr_answers', [])

    if len(hr_answers) < len(QUESTIONS):
        hr_answers.append(answer)
        session['hr_answers'] = hr_answers
        session['question_index'] = index + 1

    return jsonify({'status': 'ok'})

# Submit Final Interview Score (Optional: writes to DB)
@app.route('/submit_interview', methods=['POST'])
def submit_interview():
    match_score = float(session.get('match_score', 0))
    aptitude_score = float(session.get('aptitude_score', 0))
    technical_score = float(session.get('technical_score', 0))

    final_score = (
        match_score * 0.5 +
        aptitude_score * 0.25 +
        technical_score * 0.25
    )

    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE candidates 
                SET score = %s 
                WHERE name = %s AND designation = %s
                """,
                (final_score, session['candidate_name'], session['designation'])
            )
            connection.commit()
    finally:
        connection.close()

    return f"Final score: {final_score}"

# ✅ Corrected HR Summary Page
@app.route('/hr_summary')
def hr_summary():
    answers = session.get('hr_answers', [])  # Get stored answers
    qa_list = []

    for i, question in enumerate(QUESTIONS):
        answer = answers[i] if i < len(answers) else ""
        score = 10 if len(answer.strip()) > 5 else 0  # 10 if decent answer, 0 if empty/too short
        qa_list.append((question, answer, score))

    hr_score = sum(score for _, _, score in qa_list)

    return render_template('hr_summary.html',
                           qa_list=qa_list,
                           hr_score=hr_score)

# ==============================
# HR DASHBOARD WITH FILTERS
# ==============================
@app.route('/hr')
def hr():
    connection = get_connection()
    with connection.cursor(dictionary=True) as cursor:
        designation = request.args.get('designation')
        min_score = request.args.get('min_score')
        date = request.args.get('date')
        sort_order = request.args.get('sort_order', 'desc')

        query = "SELECT * FROM candidates WHERE 1"
        params = []

        if designation:
            query += " AND designation = %s"
            params.append(designation)

        if min_score:
            query += " AND score >= %s"
            params.append(float(min_score))

        if date:
            query += " AND DATE(uploaded_at) = %s"
            params.append(date)

        query += f" ORDER BY score {'ASC' if sort_order == 'asc' else 'DESC'}"

        cursor.execute(query, params)
        candidates = cursor.fetchall()

        cursor.execute("SELECT DISTINCT designation FROM candidates")
        designations = [row['designation'] for row in cursor.fetchall()]

    return render_template(
        'hr_dashboard.html',
        candidates=candidates,
        designations=designations
    )

# ==============================
# FILE DOWNLOAD
# ==============================
@app.route('/download/<filename>')
def download_file(filename):
    try:
        # ✅ Debug path to verify the file location
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
        else:
            return "File not found", 404
    except Exception as e:
        return f"Error downloading file: {str(e)}", 500
    
from flask import Flask, jsonify


'''@app.route('/get_questions/<designation>', methods=['GET'])
def get_questions(designation):
    try:
        questions = generate_interview_questions(designation)  # ✅ Get questions from models.py
        return jsonify(questions)  # ✅ Return as JSON response
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500'''


# ==============================
# START SERVER
# ==============================
if __name__ == '__main__':
    app.run(debug=True)

