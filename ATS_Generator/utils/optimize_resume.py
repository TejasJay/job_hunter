from openai import OpenAI
import os
from dotenv import load_dotenv
import spacy
import nltk
from nltk.corpus import stopwords
import re

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

nlp = spacy.load("en_core_web_sm")

nltk.download('stopwords')
stop_words = set(stopwords.words('english'))

EXCLUDE_WORDS = set([
    'disability', 'race', 'sex', 'color', 'pregnancy', 'status', 'law', 'protected', 'accommodations', 
    'opportunity', 'employer', 'age', 'religion', 'gender', 'identity', 'expression', 'etc',
    'equal', 'veteran', 'status', 'affirmative', 'action', 'consideration', 'accommodation', 'employment',
    'applicants', 'individual', 'rights', 'statement'
])

def clean_job_description(job_description):
    # Remove typical EEO boilerplate
    eeo_patterns = [
        r"equal opportunity employer.*?discrimination",  # catch equal opportunity employer statements
        r"applicants will not be discriminated against.*",  # other common EEO sentences
        r"accommodations.*?disability",  # accommodation disclaimers
        r"employment decisions.*?basis of",  # hiring policy boilerplate
        r"all qualified applicants.*?considered"  # inclusive hiring statements
    ]

    for pattern in eeo_patterns:
        job_description = re.sub(pattern, '', job_description, flags=re.IGNORECASE | re.DOTALL)

    return job_description

def extract_keywords_from_job_description(job_description):
    job_description = clean_job_description(job_description)

    doc = nlp(job_description)
    keywords = set()

    for chunk in doc.noun_chunks:
        keyword = chunk.text.lower().strip()
        if len(keyword) > 2 and keyword not in stop_words and keyword not in EXCLUDE_WORDS:
            keywords.add(keyword)

    for ent in doc.ents:
        if ent.label_ in ['ORG', 'PRODUCT', 'SKILL', 'TECH']:
            keywords.add(ent.text.lower().strip())

    for token in doc:
        if token.pos_ == "PROPN" and token.text.lower() not in stop_words and token.text.lower() not in EXCLUDE_WORDS:
            keywords.add(token.text.lower())

    return list(keywords)[:30]

def normalize_text(text):
    return re.sub(r'[^a-z0-9 ]', '', text.lower())

def compare_resume_to_job(resume_text, job_description):
    keywords = extract_keywords_from_job_description(job_description)
    normalized_resume = normalize_text(resume_text)
    normalized_keywords = [normalize_text(word) for word in keywords]

    matched_keywords = []
    missing_keywords = []

    for keyword in normalized_keywords:
        if keyword in normalized_resume:
            matched_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)

    score = round(100 * len(matched_keywords) / len(keywords), 2) if keywords else 0.0

    return score, missing_keywords

def get_optimized(resume_text, job_description):
    job_keywords = extract_keywords_from_job_description(job_description)

    prompt = f"""
    You are a professional resume writer and ATS optimization expert.

    Your task is to rewrite and optimize the candidate's resume for an ATS system and human recruiter, tailored for the job description below.

    The final resume should focus on the following critical factors:

    1. ✅ **Avoid Repetition**: Eliminate unnecessary repetition of words or phrases. Use varied language, synonyms, and powerful active verbs to describe achievements and responsibilities.
    2. ✅ **Resume Length**: Keep the resume to **one page** unless absolutely necessary (e.g., over 10 years of experience, academic/medical/technical fields). Include only the most **relevant and recent experience** aligned to the job description.
    3. ✅ **Bullet Points**: Use **concise bullet points** to list achievements and responsibilities. Each bullet should be **no more than 50 words**. Focus on **quantifiable results, action verbs, and measurable outcomes**.
    4. ✅ **Phone Number**: Ensure the candidate's phone number is included in the header/contact section.
    5. ✅ **Design & Format**: Output a **clean, ATS-friendly, single-column layout** using only plain text (no tables, no graphics, no images, no columns). Organize in this structure:
    - Header (Name, Location, Phone, Email, LinkedIn)
    - Professional Summary (2-3 impactful sentences)
    - Skills (keyword-rich, relevant technical and soft skills)
    - Professional Experience (reverse chronological)
    - Education
    - Certifications (if applicable)

    Additional instructions:

    ⚠️ Do NOT include any keywords or phrases related to equal opportunity, diversity, legal disclaimers, gender, age, national origin, disability, or HR policies.

    ⚠️ Focus the content entirely on the candidate's professional experience, skills, qualifications, achievements, and responsibilities aligned to the job.

    ⚠️ Do not include “keywords” lists, comments, or explanations in the output—ONLY the final optimized resume text.

    Candidate Resume:
    {resume_text}

    Job Description:
    {job_description}

    Please generate the optimized resume text below, following all the above guidelines.
    """



    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content
