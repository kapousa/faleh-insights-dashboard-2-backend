# routers/payments.py
import os
import httpx
import stripe
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, EmailStr
from src.setup.settings import settings
from db import get_connection

router = APIRouter(prefix="/api/payments", tags=["payments"])
stripe.api_key = settings.stripe_api_key
FRONTEND_URL = settings.frontend_url
STRIPE_REPORT_PRICE_ID = settings.stripe_report_price_id

# ─── Webhook verification + forwarding ───
# n8n's raw-body handling is version-inconsistent, which made HMAC
# verification unreliable there. Verifying here instead is much more
# solid — FastAPI gets true raw bytes trivially via request.body(), and
# Stripe's own SDK (construct_event) handles the HMAC + timestamp check.
STRIPE_WEBHOOK_SECRET = settings.stripe_webhook_secret
N8N_FORWARD_URL = settings.n8n_forward_url  # e.g. https://faleh-faleh-n8n.qvyj0e.easypanel.host/webhook/stripe-checkout
INTERNAL_WEBHOOK_SECRET = settings.internal_webhook_secret # shared secret, FastAPI <-> n8n only


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

    # Use .to_dict() — Stripe's StripeObject doesn't support plain dict()
    # conversion (it breaks with KeyError on integer index).
    metadata = session.metadata.to_dict() if session.metadata else {}
    submission_id = metadata.get("submission_id")

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

    # Convert invoice StripeObject to dict for safe field access
    invoice_dict = invoice.to_dict() if invoice else {}

    return {
        "paid": session.payment_status == "paid",
        "email": session.customer_details.email if session.customer_details else None,
        "report_url": report_url,
        "report_ready": report_url is not None,
        "invoice_url": invoice_dict.get("hosted_invoice_url"),
        "invoice_pdf": invoice_dict.get("invoice_pdf"),
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    """
    Receives Stripe's webhook directly. Verifies the signature properly
    (true raw bytes, no parsing ambiguity), then forwards the exact same
    raw payload on to n8n for the actual business logic — n8n no longer
    re-verifies the Stripe signature itself, it just trusts this forward
    based on the shared INTERNAL_WEBHOOK_SECRET header.
    """
    payload = await request.body()

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    try:
        stripe.Webhook.construct_event(payload, stripe_signature, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        # Catch broadly here on purpose — different stripe-python SDK
        # versions raise slightly different exception types for a bad
        # signature, and we want a clean 400 (not a bare 500) either way,
        # plus a full traceback in the logs so we can see exactly what
        # Stripe's SDK actually raised.
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Signature verification failed: {e}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                N8N_FORWARD_URL,
                content=payload,  # forward the exact original bytes, unchanged
                headers={
                    "Content-Type": "application/json",
                    "x-internal-secret": INTERNAL_WEBHOOK_SECRET,
                },
            )
        return {"received": True, "forwarded": True, "n8n_status": resp.status_code}
    except Exception as e:
        # Same idea — n8n being briefly unreachable shouldn't 500 back to
        # Stripe (that just triggers pointless retries), but we DO want the
        # real exception visible in logs since it means the report/email
        # chain silently won't fire for this event.
        import traceback
        traceback.print_exc()
        print(f"[stripe_webhook] Failed to forward verified event to n8n: {e}")
        return {"received": True, "forwarded": False}