# routers/assessments.py
import json
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import get_connection

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


class AssessmentPayload(BaseModel):
    businessDetails: dict
    contactInfo: dict
    wizardAnswers: list
    assessmentResults: dict
    timestamp: str


class AssessmentSubmitResponse(BaseModel):
    submission_id: str


@router.post("/submit", response_model=AssessmentSubmitResponse)
def submit_assessment(payload: AssessmentPayload):
    """
    Saves the raw wizard answers to Postgres. Deliberately does NOT call the
    Executive Summary / report-generation flow here — that only happens
    after payment succeeds (triggered by the Stripe webhook), so we never
    pay for report generation on submissions that don't convert.
    """
    submission_id = str(uuid.uuid4())

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO assessment_submissions
                        (id, business_details, contact_info, wizard_answers,
                         assessment_results, submitted_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        submission_id,
                        json.dumps(payload.businessDetails),
                        json.dumps(payload.contactInfo),
                        json.dumps(payload.wizardAnswers),
                        json.dumps(payload.assessmentResults),
                        payload.timestamp,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save assessment: {e}")

    return AssessmentSubmitResponse(submission_id=submission_id)