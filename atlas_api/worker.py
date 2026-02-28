"""Background worker to consume Redis events for usage tracking."""

import asyncio
import json
import logging
import redis.asyncio as aioredis

from atlas_api.config import ApiConfig
from atlas_api.db import get_db_pool

logger = logging.getLogger(__name__)

async def run_usage_worker(config: ApiConfig):
    """Consume atlas.ai.usage and atlas.scan.requests events."""
    logger.info("Starting usage worker connected to %s", config.redis_url)
    client = aioredis.from_url(config.redis_url, decode_responses=True)
    
    # Create groups
    for stream in ["atlas.ai.usage", "atlas.scan.requests"]:
        try:
            await client.xgroup_create(stream, "atlas-api-usage", id="0", mkstream=True)
        except aioredis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                logger.warning("Failed to create group for %s: %s", stream, e)

    while True:
        try:
            messages = await client.xreadgroup(
                "atlas-api-usage",
                "atlas-api-1",
                {"atlas.ai.usage": ">", "atlas.scan.requests": ">"},
                count=10,
                block=5000
            )
            
            if not messages:
                continue
                
            pool = await get_db_pool()
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    for stream, entries in messages:
                        for msg_id, fields in entries:
                            try:
                                payload = json.loads(fields.get("payload", "{}"))
                                tenant_id = payload.get("tenant_id") or payload.get("metadata", {}).get("tenant_id", "default")
                                
                                # Use ON CONFLICT DO UPDATE so we always have a row
                                await cur.execute(
                                    """
                                    INSERT INTO tenants (id, name, plan_tier)
                                    VALUES (%s, %s, 'free')
                                    ON CONFLICT (id) DO NOTHING
                                    """,
                                    (tenant_id, tenant_id)
                                )
                                await cur.execute(
                                    """
                                    INSERT INTO tenant_usage (tenant_id, scans_count, token_count)
                                    VALUES (%s, 0, 0)
                                    ON CONFLICT (tenant_id) DO NOTHING
                                    """,
                                    (tenant_id,)
                                )
                                
                                if stream == "atlas.ai.usage":
                                    tokens = payload.get("tokens_used", 0)
                                    await cur.execute(
                                        "UPDATE tenant_usage SET token_count = token_count + %s, last_updated = NOW() WHERE tenant_id = %s",
                                        (tokens, tenant_id)
                                    )
                                    logger.info("Tracked %d tokens for tenant %s", tokens, tenant_id)
                                    
                                elif stream == "atlas.scan.requests":
                                    await cur.execute(
                                        "UPDATE tenant_usage SET scans_count = scans_count + 1, last_updated = NOW() WHERE tenant_id = %s",
                                        (tenant_id,)
                                    )
                                    logger.info("Tracked scan request for tenant %s", tenant_id)
                            except Exception as e:
                                logger.error("Usage worker error processing %s: %s", msg_id, e)
                            finally:
                                await client.xack(stream, "atlas-api-usage", msg_id)
                                
                await conn.commit()
                
        except asyncio.CancelledError:
            logger.info("Usage worker cancelled")
            break
        except Exception as e:
            logger.error("Usage worker connection error: %s", e)
            await asyncio.sleep(5)
