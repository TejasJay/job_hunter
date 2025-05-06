from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from utils import parse_resume, generate_doc
from utils.optimize_resume import compare_resume_to_job, get_optimized

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze/")
async def analyze(request: Request, resume: UploadFile, job_description: str = Form(...)):
    filename = f"uploads/{resume.filename}"
    with open(filename, "wb") as f:
        f.write(await resume.read())

    resume_text = parse_resume.extract_text(filename)
    match_score, missing_keywords = compare_resume_to_job(resume_text, job_description)
    optimized_resume = get_optimized(resume_text, job_description)

    out_file = generate_doc.create_pdf(optimized_resume, resume.filename)

    return templates.TemplateResponse("result.html", {
        "request": request,
        "score": match_score,
        "missing": missing_keywords,
        "download_link": f"/download/{os.path.basename(out_file)}"
    })

@app.get("/download/{filename}")
async def download(filename: str):
    return FileResponse(f"optimized/{filename}", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=filename)
