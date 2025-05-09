from pydantic import BaseModel

class RankResponse(BaseModel):
    final_score: float
    section_scores: dict
    missing_skills: list
    recommendations: list
