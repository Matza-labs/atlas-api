"""Billing routes for Stripe integrations."""

import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

from atlas_api.db import get_db_connection
from atlas_api.dependencies import get_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()

class CheckoutSessionRequest(BaseModel):
    plan_id: str

class CheckoutSessionResponse(BaseModel):
    url: str

@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CheckoutSessionRequest,
    tenant_id: str = Depends(get_tenant_id),
    conn = Depends(get_db_connection)
):
    """Create a Stripe checkout session for a tenant."""
    # In a real integration, we would call the Stripe API here.
    logger.info("Creating checkout session for tenant %s with plan %s", tenant_id, request.plan_id)
    return CheckoutSessionResponse(
        url=f"https://checkout.stripe.com/pay/cs_test_mock_{tenant_id}_{request.plan_id}"
    )

@router.post("/webhook")
async def stripe_webhook(request: Request, conn = Depends(get_db_connection)):
    """Handle Stripe webhooks."""
    try:
        data = await request.json()
        event_type = data.get("type", "unknown")
        logger.info("Received stripe webhook event: %s", event_type)
        
        if event_type == "customer.subscription.updated":
            # Extract customer ID and update tenant plan in DB
            pass
            
    except Exception as e:
        logger.error("Error processing webhook: %s", e)
        raise HTTPException(status_code=400, detail="Webhook processing failed")
        
    return {"status": "success"}

@router.get("/status")
async def get_billing_status(
    tenant_id: str = Depends(get_tenant_id),
    conn = Depends(get_db_connection)
):
    """Get the current billing status and usage for a tenant."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT t.plan_tier, tu.scans_count, tu.token_count
            FROM tenants t
            LEFT JOIN tenant_usage tu ON t.id = tu.tenant_id
            WHERE t.id = %s
            """,
            (tenant_id,)
        )
        row = await cur.fetchone()
        
    if not row:
        return {"plan_tier": "free", "scans_count": 0, "token_count": 0}
        
    return {
        "plan_tier": row[0],
        "scans_count": row[1] or 0,
        "token_count": row[2] or 0
    }
