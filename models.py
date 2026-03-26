import spacy
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from database import get_connection
import re
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from flask import session


nlp = spacy.load("en_core_web_sm")

def extract_skills(text):
    skills = [
        'python', 'java', 'javascript', 'html', 'css', 'react', 'redux', 
        'angular', 'nodejs', 'express', 'django', 'flask', 'spring boot', 
        'docker', 'kubernetes', 'rest api', 'graphql', 'aws', 'azure',
        'microservices', 'git', 'mysql', 'postgresql', 'mongodb'
    ]
    
    found_skills = set()
    text = text.lower()
    
    for skill in skills:
        if re.search(rf'\b{re.escape(skill)}\b', text):
            found_skills.add(skill)
    
    return list(found_skills)


def get_required_skills_from_db(designation):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT skills FROM job_descriptions WHERE designation = %s", (designation,))
        result = cursor.fetchone()
        if result:
            # ✅ Split comma-separated skills, remove extra spaces
            skills = [skill.strip().lower() for skill in result[0].split(',')]
            return skills
        else:
            return []  # No skills found for the designation
    finally:
        connection.close()

def analyze_resume(resume_text, designation):
    resume_text = resume_text.lower()  # Convert to lowercase for case-insensitive matching
    required_skills = get_required_skills_from_db(designation.lower())

    if not required_skills:
        return 0.0, []

    # ✅ Debug: Print required skills from the database
    print(f"\n[DEBUG] Required Skills for '{designation}': {required_skills}")

    # ✅ Normalize and clean up skills
    required_skills = list(set(skill.strip().lower() for skill in required_skills))

    # ✅ Debug: Print ONLY first 500 characters for logging (BUT process entire resume)
    print(f"\n[DEBUG] First 500 Characters of Resume:\n{resume_text[:500]}...")

    # ✅ Try to find skills in resume (Full Text)
    found_skills = set()
    for skill in required_skills:
        pattern = r'\b' + re.escape(skill) + r'\b'  # Match exact word boundaries
        if re.search(pattern, resume_text):
            found_skills.add(skill)

    # ✅ Debug: Print matched skills
    print(f"\n[DEBUG] Matched Skills: {found_skills}")

    # ✅ Calculate match score
    match_score = (len(found_skills) / len(required_skills)) * 100 if required_skills else 0

    # ✅ Debug: Print missing skills
    missing_skills = list(set(required_skills) - found_skills)
    print(f"\n[DEBUG] Missing Skills: {missing_skills}")

    return round(match_score, 2), missing_skills


def calculate_match(resume_text, job_description):
    """
    ✅ Calculate match score using Cosine Similarity
    """
    texts = [resume_text, job_description]
    cv = CountVectorizer().fit_transform(texts)
    similarity = cosine_similarity(cv)[0][1]
    return similarity

def get_interview_structure(designation):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT aptitude_questions, technical_questions, hr_questions FROM job_structure WHERE designation = %s",
            (designation,)
        )
        result = cursor.fetchone()
        if result:
            return {
                'aptitude_questions': result['aptitude_questions'],
                'technical_questions': result['technical_questions'],
                'hr_questions': result['hr_questions']
            }
        else:
            # ✅ Default interview structure if not found
            return {
                'aptitude_questions': 10,
                'technical_questions': 5,
                'hr_questions': 3
            }
    finally:
        connection.close()

'''import json

def generate_interview_questions(designation):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # ✅ Step 1: Get structure
        structure = get_interview_structure(designation)
        aptitude_count = structure['aptitude_questions']
        technical_count = structure['technical_questions']
        hr_count = structure['hr_questions']

        questions = {
            'aptitude': [],
            'technical': [],
            'hr': []
        }

        # ✅ Step 2: Get Aptitude Questions
        cursor.execute(
            "SELECT question, options, correct_answer FROM questions WHERE type = 'aptitude' ORDER BY RAND() LIMIT %s",
            (aptitude_count,)
        )
        aptitude_questions = cursor.fetchall()

        for q in aptitude_questions:
            if isinstance(q['options'], str):
                try:
                    q['options'] = json.loads(q['options'])
                except json.JSONDecodeError:
                    q['options'] = []

        questions['aptitude'] = aptitude_questions

        # ✅ Step 3: Get Technical Questions
        cursor.execute(
            "SELECT question, options, correct_answer FROM questions WHERE type = 'technical' AND designation = %s ORDER BY RAND() LIMIT %s",
            (designation, technical_count)
        )
        technical_questions = cursor.fetchall()

        for q in technical_questions:
            if isinstance(q['options'], str):
                try:
                    q['options'] = json.loads(q['options'])
                except json.JSONDecodeError:
                    q['options'] = []

        questions['technical'] = technical_questions

        # ✅ Step 4: Get HR Questions
        cursor.execute(
            "SELECT question FROM questions WHERE type = 'hr' ORDER BY RAND() LIMIT %s",
            (hr_count,)
        )
        hr_questions = cursor.fetchall()
        questions['hr'] = [q['question'] for q in hr_questions]

        # ✅ Save questions to session (IMPORTANT)
        session['aptitude_questions'] = questions['aptitude']
        session['technical_questions'] = questions['technical']
        session['hr_questions'] = questions['hr']

        print("\n[DEBUG] Saved to Session:", session['aptitude_questions'])

        return questions

    finally:
        connection.close()


'''