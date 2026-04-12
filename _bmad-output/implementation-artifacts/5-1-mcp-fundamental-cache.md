# Story 5.1: MCP-Fundamental-Abruf mit TTL-Cache

Status: ready-for-dev

## Story

As a Chef,
I want the system to fetch fundamental assessments from Viktor and Satoshi via MCP,
so that I have AI analyst opinions available for my trade decisions.

## Acceptance Criteria

1. **Given** ein Asset-Symbol, **When** eine Fundamental-Einschaetzung angefragt wird, **Then** ruft das System via MCP Viktor (Aktien/SFA) oder Satoshi (Crypto/CFA) ab (FR19)
2. **Given** ein Fundamental-Ergebnis, **When** gecached, **Then** wird es mit cached_at-Timestamp gespeichert; TTL: 15 Minuten fuer Crypto, 1 Stunde fuer Aktien (FR22, NFR-I2)
3. **Given** ein gecachtes Ergebnis, **When** im UI angezeigt, **Then** zeigt eine Staleness-Anzeige "Stand: vor X Minuten" den Zeitpunkt der letzten Aktualisierung (FR22)
4. **Given** den MCP-Client, **When** ein Call ausgefuehrt wird, **Then** wird der 10s-Timeout aus dem MCP-Wrapper (Story 1.6) erzwungen; bei Timeout wird der Cache-Fallback mit Staleness-Banner verwendet (NFR-I1)

## Tasks / Subtasks

- [ ] Task 1: Fundamental-Service (AC: 1)
  - [ ] `app/services/fundamental.py` — `get_fundamental(symbol, asset_class)`
  - [ ] Routing: asset_class=='stock' → Viktor; 'crypto' → Satoshi
  - [ ] MCP-Call via Story 1.6 Wrapper
- [ ] Task 2: TTL-Cache Layer (AC: 2, 4)
  - [ ] `cachetools.TTLCache` als In-Memory-Cache
  - [ ] TTL unterschiedlich: 900s Crypto, 3600s Aktien
  - [ ] Cache-Key: `(symbol, asset_class)`
  - [ ] Cache-Value: `(response, cached_at_timestamp)`
- [ ] Task 3: Staleness-Tracking (AC: 3)
  - [ ] cached_at im Cache-Value
  - [ ] Helper: `format_staleness(cached_at)` → "vor X Minuten"
- [ ] Task 4: Cache-Fallback bei Timeout (AC: 4)
  - [ ] Bei asyncio.TimeoutError: check ob Stale-Cache existiert
  - [ ] Return Stale-Cache mit Flag `is_stale=True`
  - [ ] Trigger Staleness-Banner in UI
- [ ] Task 5: Unit-Tests (AC: 1, 2, 3, 4)
  - [ ] Mock MCP-Client
  - [ ] Test: Fresh cache hit → Cache-Response
  - [ ] Test: Stale cache + timeout → Fallback
  - [ ] Test: Miss + success → MCP-Call + cache

## Dev Notes

**Fundamental-Service-Pattern:**
```python
from cachetools import TTLCache
from datetime import datetime

_cache = {}  # Per-asset-class TTLCaches
_cache['crypto'] = TTLCache(maxsize=500, ttl=900)   # 15 min
_cache['stock'] = TTLCache(maxsize=500, ttl=3600)   # 1 hour

async def get_fundamental(
    symbol: str,
    asset_class: str,
    mcp_client: MCPClient,
) -> FundamentalResult:
    cache = _cache[asset_class]
    cache_key = symbol

    # Try fresh cache
    if cache_key in cache:
        cached = cache[cache_key]
        return FundamentalResult(
            data=cached['data'],
            cached_at=cached['cached_at'],
            is_stale=False,
        )

    # Fetch from MCP
    agent = "viktor" if asset_class == "stock" else "satoshi"
    try:
        response = await mcp_client.call(
            tool="fundamentals",
            agent=agent,
            symbol=symbol,
        )
        cache[cache_key] = {
            'data': response,
            'cached_at': datetime.utcnow(),
        }
        return FundamentalResult(data=response, cached_at=datetime.utcnow(), is_stale=False)

    except (asyncio.TimeoutError, ConnectionError) as e:
        # Fallback to stale cache (even beyond TTL)
        stale = _stale_storage.get(cache_key)
        if stale:
            return FundamentalResult(
                data=stale['data'],
                cached_at=stale['cached_at'],
                is_stale=True,
            )
        raise
```

**Stale-Storage:**
Separater Dict ohne TTL fuer Fallback-Only-Cache (wird bei erfolgreichem Call aktualisiert):
```python
_stale_storage = {}  # Long-term fallback
```

**FundamentalResult Model:**
```python
class FundamentalResult(BaseModel):
    data: dict  # MCP response payload
    cached_at: datetime
    is_stale: bool
```

**Usage (in Story 5.2):**
```python
result = await get_fundamental("AAPL", "stock", mcp_client)
# In Template:
# "Stand: vor 23 Minuten" if not result.is_stale
# "⚠ Stand: vor 3 Stunden (MCP-Outage)" if result.is_stale
```

**File Structure:**
```
app/
├── models/
│   └── fundamental.py        # NEW
├── services/
│   ├── fundamental.py        # NEW - cached fetch
│   └── staleness.py          # NEW - format helpers
```

### References

- PRD: FR19, FR22, NFR-I1, NFR-I2
- Architecture: "In-Memory TTL-Cache", "MCP Integration"
- Dependency: Story 1.6 (MCP-Client-Wrapper), Story 1.3 (taxonomy fuer agent-routing)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
