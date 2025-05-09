# File Structure

ats_project/
├── app/
│   ├── main.py                  → FastAPI app entrypoint
│   ├── api.py                   → FastAPI route definitions
│   ├── models/                  → ML models and embedding setup
│   │   ├── embedding.py         → load BERT / SentenceTransformer
│   │   ├── ranking_model.py     → train_ranking_model, update_ranking_model
│   ├── utils/                   → Core ATS logic modules
│   │   ├── section_parser.py    → parse_resume_sections, compute_section_weights
│   │   ├── semantic_matcher.py  → semantic_match_resume_to_jd, compute_tfidf_similarity, compute_bert_similarity
│   │   ├── skill_normalizer.py  → normalize_skills
│   │   ├── ner_extractor.py     → extract_named_entities, extract_and_rank_entities
│   │   ├── timeline_analyzer.py → analyze_experience_timeline
│   │   ├── title_matcher.py     → match_titles_and_seniority
│   │   ├── soft_skills.py       → detect_soft_skills_and_leadership
│   │   ├── quality_checker.py   → evaluate_resume_quality
│   │   ├── bias_filter.py       → anonymize_resume
│   │   ├── feedback.py          → log_and_apply_feedback
│   ├── pipeline.py              → parse_and_preprocess_resume, score_resume_against_job, generate_recruiter_report
│   └── schemas.py               → Pydantic request/response models
├── data/
│   ├── skill_database.json      → canonical skill mappings
│   ├── soft_skill_patterns.json → regex patterns for soft skills
│   └── example_jd.txt           → sample job description
├── requirements.txt             → Python package dependencies
└── README.md                    → Project documentation



* * *

# Function Layout


### ✅ A. Section-level parsing and weighting

```python
def parse_resume_sections(resume_text):
    """
    Splits the resume into sections: experience, education, skills, certifications, projects.
    Returns a dictionary {section_name: section_content}.
    """

def compute_section_weights(section_scores):
    """
    Applies weights to each section score:
    Experience (40%), Skills (30%), Education (10%), Certifications (10%), Soft Skills (10%).
    Returns a json of {section score, weighted overall score, sections present, sections not present}.
    """
```

* * *

### ✅ B. Semantic keyword + concept matching

```python
def semantic_match_resume_to_jd(resume_text, job_description, embedding_model):
    """
    Uses sentence embeddings (BERT, SentenceTransformer) to compute semantic similarity
    between resume and job description.
    Returns similarity score and top matching concepts.
    """
```

* * *

### ✅ C. Skills normalization + synonym mapping

```python
def normalize_skills(skills_list, skill_database):
    """
    Maps raw resume skills to canonical forms using a skill database or synonym map.
    Example: maps 'JS' and 'JavaScript' to 'JavaScript'.
    Returns normalized list of skills.
    """
```

* * *

### ✅ D. Named entity extraction

```python
def extract_named_entities(resume_text, ner_model):
    """
    Uses spaCy or BERT-based NER to extract entities:
    Companies, Job Titles, Degrees, Certifications, Dates.
    Returns structured data with extracted entities.
    """
```

* * *

### ✅ E. Experience timeline analysis

```python
def analyze_experience_timeline(entities):
    """
    Analyzes start and end dates of experience sections.
    Computes total years of experience, detects gaps or jumps.
    Checks for progressive seniority.
    Returns timeline metrics and flags.
    """
```

* * *

### ✅ F. Title and seniority match

```python
def match_titles_and_seniority(resume_titles, target_title, embedding_model):
    """
    Compares resume job titles to target job title using semantic similarity.
    Determines if seniority level matches (junior, mid, senior).
    Returns similarity score and seniority classification.
    """
```

* * *

### ✅ G. Soft skills + leadership signal detection

```python
def detect_soft_skills_and_leadership(resume_text, soft_skill_patterns):
    """
    Uses regex patterns or NLP phrase matching to detect soft skills and leadership signals.
    Example: 'led a team', 'mentored', 'managed budget'.
    Returns list of detected soft skills.
    """
```

* * *

### ✅ H. Resume quality metrics

```python
def evaluate_resume_quality(file_path, resume_text):
    """
    Evaluates resume file type, length, readability, and typos.
    Penalizes for low readability or excessive length.
    Returns quality score and recommendations.
    """
```

* * *

### ✅ I. Diversity + bias mitigation

```python
def anonymize_resume(resume_text):
    """
    Removes sensitive demographic information (name, address, gender, nationality)
    to reduce bias in ranking.
    Returns anonymized resume text.
    """
```

* * *

### ✅ J. Learning feedback loop

```python
def update_ranking_model(feedback_data, ranking_model):
    """
    Incorporates recruiter feedback (shortlisted, rejected, hired)
    into the machine learning ranking model.
    Updates the model weights over time.
    Returns the updated ranking model.
    """
```

* * *

### ⚙ Advanced algorithm components

```python
def compute_tfidf_similarity(resume_text, jd_text):
    """
    Uses TF-IDF + cosine similarity to compare resume to job description.
    Returns a similarity score.
    """

def compute_bert_similarity(resume_text, jd_text, embedding_model):
    """
    Uses BERT or Sentence-BERT embeddings to compute semantic similarity.
    Returns a similarity score.
    """

def extract_and_rank_entities(resume_text):
    """
    Extracts job titles, companies, dates, and degrees, then ranks
    based on relevance to job description.
    Returns ranked entities.
    """

def train_ranking_model(training_data):
    """
    Trains an ML ranking model (e.g., LightGBM, XGBoost) on labeled data.
    Returns trained model.
    """

def log_and_apply_feedback(resume_id, recruiter_action):
    """
    Logs recruiter feedback and uses it to adjust candidate rankings over time.
    Returns updated feedback log.
    """
```

* * *

### 📂 High-level pipeline controller functions

```python
def parse_and_preprocess_resume(file_path):
    """
    Loads resume file, extracts text, parses sections, and runs NER.
    Returns structured resume object.
    """

def score_resume_against_job(resume, job_description, models):
    """
    Runs all scoring modules:
    section weights, semantic matching, skill normalization,
    title match, soft skill detection, quality checks, and bias mitigation.
    Returns final ATS score breakdown.
    """

def generate_recruiter_report(resume_score, missing_skills, recommendations):
    """
    Generates a detailed report with match scores, missing keywords,
    resume quality feedback, and actionable insights.
    Returns report object.
    """
```

* * *


