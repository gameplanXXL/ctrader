"""External-service clients — broker APIs, MCP, OHLC sources.

Each module wraps one external dependency with a single canonical entry
point so services and routers never touch raw `httpx`/`asyncpg`/Protobuf
calls directly. Keeps timeouts, retries, and graceful-degradation logic
in one place per integration.
"""
