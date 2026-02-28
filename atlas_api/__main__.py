"""Entry point for running atlas-api as a module.

Usage:
    python -m atlas_api                         # default host/port
    python -m atlas_api --host 0.0.0.0 --port 8080
    python -m atlas_api --reload                # auto-reload for development

Environment variables override defaults; CLI flags override env vars.
"""

from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="PipelineAtlas REST API server")
    parser.add_argument(
        "--host",
        default=os.environ.get("ATLAS_API_HOST", "0.0.0.0"),
        help="Bind host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ATLAS_API_PORT", "8000")),
        help="Bind port (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (development only)",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("ATLAS_API_LOG_LEVEL", "info"),
        help="Uvicorn log level (default: info)",
    )
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "atlas_api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
