# routers/payments.py
import os
import stripe
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from db import get_connection

router = APIRouter(prefix="/api/payments", tags=["payments"])
stripe.api_key = os.environ.get("STRIPE_API_KEY")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://faleh.franchisemiddleeast.com")
STRIPE_REPORT_PRICE_ID = os.environ.get("STRIPE_REPORT_PRICE_ID")


class CreateCheckoutRequest(BaseModel):
    customer_email: EmailStr
    submission_id: str  # references assessment_submissions.id in Postgres


class CreateCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/create-checkout-session", response_model=CreateCheckoutResponse)
def create_checkout_session(payload: CreateCheckoutRequest):
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=payload.customer_email,
            line_items=[
                {"price": STRIPE_REPORT_PRICE_ID, "quantity": 1}
            ],
            # Generates a real Stripe Invoice for this payment — gives us
            # hosted_invoice_url + invoice_pdf after payment.
            invoice_creation={"enabled": True},
            metadata={
                # No report_url yet — the report doesn't exist until the
                # webhook generates it AFTER payment succeeds.
                "submission_id": payload.submission_id,
            },
            success_url=f"{FRONTEND_URL}/confirm?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/checkout-cancelled",
        )
        return CreateCheckoutResponse(checkout_url=session.url, session_id=session.id)
    except stripe.error.StripeError as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session/{session_id}")
def get_checkout_session(session_id: str):
    try:
        # expand=["invoice"] gets the full invoice object (not just its ID)
        # in one call, so we can return hosted_invoice_url/invoice_pdf directly.
        session = stripe.checkout.Session.retrieve(session_id, expand=["invoice"])
    except stripe.error.InvalidRequestError:
        raise HTTPException(status_code=404, detail="Session not found")

    invoice = session.invoice  # expanded object, or None
    submission_id = session.metadata.get("submission_id") if session.metadata else None

    # The report only exists once the n8n webhook has finished calling the
    # Executive Summary flow and written report_url back to Postgres.
    # The frontend polls this endpoint until report_ready flips to true.
    report_url = None
    if submission_id:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT report_url FROM assessment_submissions WHERE id = %s",
                    (submission_id,),
                )
                row = cur.fetchone()
                if row:
                    report_url = row[0]
        finally:
            conn.close()

    return {
        "paid": session.payment_status == "paid",
        "email": session.customer_details.email if session.customer_details else None,
        "report_url": report_url,
        "report_ready": report_url is not None,
        "invoice_url": invoice.hosted_invoice_url if invoice else None,
        "invoice_pdf": invoice.invoice_pdf if invoice else None,
    }