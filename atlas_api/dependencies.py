"""Shared dependencies for FastAPI routes."""

from fastapi import Header, HTTPException


def get_tenant_id(x_tenant_id: str = Header(default="", alias="X-Tenant-Id")) -> str:
    """FastAPI dependency to enforce multi-tenant isolation.
    
    If the header is missing, we reject the request.
    In real SaaS, we would decode a JWT or Check an API Key.
    """
    tenant_id = x_tenant_id.strip()
    if not tenant_id:
        raise HTTPException(status_code=401, detail="X-Tenant-Id header is required")
    return tenant_id
