from fastapi import APIRouter, UploadFile, Form
from app.pipeline import parse_and_preprocess_resume, score_resume_against_job, generate_recruiter_report

router = APIRouter()

@router.post("/rank_resume/")
async def rank_resume(file: UploadFile, job_description: str = Form(...)):
    resume = await parse_and_preprocess_resume(file)
    score = await score_resume_against_job(resume, job_description)
    report = await generate_recruiter_report(score)
    return report
