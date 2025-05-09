import re
import pdfplumber
import json
import pprint

pdf_path = "data/resume.pdf"
section_keywords_path = "data/section_directory.json"

# Sample section keywords for boosting (optional)
section_keywords = {
    "experience": ["developed", "managed", "led", "built", "designed", "implemented"],
    "skills": ["python", "sql", "machine learning", "docker", "aws", "tensorflow"],
    "education": ["bachelor", "master", "phd", "university", "gpa", "degree"],
    "certifications": ["certified", "license", "course", "training", "certificate"],
    "projects": ["built", "designed", "implemented", "github", "collaborated"]
}

def extract_text_from_pdf(pdf_path):
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        print(f"Error Extracting text from PDF: {e}")
        return None


def parse_resume_sections(resume_text):
    with open(section_keywords_path, "r") as file:
        section_aliases = json.load(file)

    result = {section: "" for section in section_aliases}
    current_section = None

    for line in resume_text.splitlines():
        line_clean = line.strip().lower()

        matched_section = None
        for section, aliases in section_aliases.items():
            if any(re.fullmatch(rf"{re.escape(alias)}", line_clean) for alias in aliases):
                matched_section = section
                break

        if matched_section:
            current_section = matched_section
            continue

        if current_section:
            result[current_section] += line + "\n"

    return result


def score_section_content(section_text, keywords=None):
    lines = [line for line in section_text.splitlines() if line.strip()]
    base_score = min(len(lines), 10)

    if not lines:
        return 0

    keyword_score = 0
    if keywords:
        text_lower = section_text.lower()
        keyword_score = sum(text_lower.count(kw) for kw in keywords)
        keyword_score = min(keyword_score, 5)

    return min(base_score + keyword_score, 10)


def compute_section_weights(section_scores):
    weights = {
        "experience": 50,
        "skills": 40,
        "education": 5,
        "certifications": 2.5,
        "projects": 2.5
    }

    total_score = 0
    for section, score in section_scores.items():
        weight = weights.get(section, 0)
        total_score += score * (weight / 100)

    return round(total_score, 2)


def compute_resume_score(resume_text):
    parsed_sections = parse_resume_sections(resume_text)

    section_scores = {}
    sections_present = []
    sections_not_present = []

    for section, content in parsed_sections.items():
        if content.strip():
            sections_present.append(section)
            section_scores[section] = score_section_content(content, section_keywords.get(section))
        else:
            sections_not_present.append(section)

    final_score = compute_section_weights(section_scores)

    result = {
        "sections_present": sections_present,
        "sections_not_present": sections_not_present,
        "scores": section_scores,
        "final_weighted_score": final_score
    }

    return result


# MAIN EXECUTION
resume_text = extract_text_from_pdf(pdf_path)
if resume_text is not None:
    result = compute_resume_score(resume_text)
    pprint.pprint(result)
