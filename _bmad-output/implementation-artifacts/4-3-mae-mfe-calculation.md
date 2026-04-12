# Story 4.3: MAE/MFE-Berechnung

Status: ready-for-dev

## Story

As a Chef,
I want to see Maximum Adverse and Favorable Excursion for each trade,
so that I can evaluate my entry timing and stop-loss placement.

## Acceptance Criteria

1. **Given** einen Trade mit bekanntem Zeitraum, **When** der Drilldown geladen wird, **Then** werden MAE und MFE angezeigt — jeweils in Preis-Einheiten und Position-Dollar-Einheiten (FR13a)
2. **Given** die App startet mit neuer Migration, **When** migrate laeuft, **Then** wird die `ohlc_candles`-Tabelle erstellt mit: id, symbol, timeframe (enum: '1m','5m'), ts (TIMESTAMPTZ), open, high, low, close, volume, cached_at (TIMESTAMPTZ), UNIQUE (symbol, timeframe, ts), `idx_ohlc_candles_symbol_ts` Index
3. **Given** einen Trade, **When** MAE/MFE berechnet werden soll, **Then** werden Intraday-Candle-Daten (1m/5m) via ib_async reqHistoricalData() geholt; bei Fehler Fallback auf Binance/Kraken API oder fundamental/price MCP
4. **Given** die Candle-Daten, **When** geholt, **Then** werden sie in der ohlc_candles-Tabelle mit 24h TTL gecached (Cache-Lookup prueft `cached_at > now() - interval '24 hours'`) (NFR-I6)
5. **Given** die Datenquelle ist nicht erreichbar, **When** MAE/MFE berechnet werden soll, **Then** werden die Felder als NULL angezeigt (Graceful Degradation) mit Timeout <= 15s (NFR-I6)

## Tasks / Subtasks

- [ ] Task 1: Migration 004_ohlc_candles_table.sql (AC: 2)
  - [ ] Tabelle mit allen Spalten
  - [ ] UNIQUE constraint
  - [ ] Index fuer (symbol, timeframe, ts)
- [ ] Task 2: ohlc_candles-Modelle (AC: 2)
  - [ ] `app/models/ohlc.py` mit Pydantic
  - [ ] Enum timeframe
- [ ] Task 3: OHLC-Client Abstraction (AC: 3, 5)
  - [ ] `app/clients/ohlc.py` mit `OHLCClient` Interface
  - [ ] Implementierungen: IBHistoricalClient, BinanceClient, KrakenClient, FundamentalPriceClient
  - [ ] Fallback-Chain: IB → Binance → Kraken → MCP
  - [ ] Timeout 15s via `asyncio.wait_for`
- [ ] Task 4: Cache-Layer (AC: 4)
  - [ ] `app/services/ohlc_cache.py`
  - [ ] Lookup: SELECT aus ohlc_candles WHERE cached_at > now() - 24h
  - [ ] Miss: Fetch via Client → UPSERT
- [ ] Task 5: MAE/MFE-Berechnung (AC: 1)
  - [ ] `app/services/mae_mfe.py` — `compute_mae_mfe(trade) -> (mae, mfe)`
  - [ ] Logic: Zieh Candles zwischen opened_at und closed_at
  - [ ] MAE = MIN(low) (fuer long) oder MAX(high) (fuer short) relative zu entry
  - [ ] MFE = MAX(high) (long) oder MIN(low) (short) relative zu entry
  - [ ] Dollar-Units = price_excursion * quantity
- [ ] Task 6: Trade-Drilldown Integration (AC: 1)
  - [ ] `fragments/trade_detail.html` — MAE/MFE-Section
  - [ ] Bei NULL: "— (data unavailable)" in --text-muted
- [ ] Task 7: Graceful Degradation Test (AC: 5)
  - [ ] Mock: alle OHLC-Clients failen
  - [ ] Assert: Drilldown zeigt NULL, kein Exception
  - [ ] Timeout respektiert (<15s)

## Dev Notes

**ohlc_candles Schema:**
```sql
CREATE TYPE timeframe AS ENUM ('1m', '5m');

CREATE TABLE ohlc_candles (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe timeframe NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC,
    cached_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, timeframe, ts)
);
CREATE INDEX idx_ohlc_candles_symbol_ts ON ohlc_candles(symbol, timeframe, ts);
```

**MAE/MFE Formeln:**
```
Long-Position (Entry=100, Exit=105):
  MAE = min(low during trade) - 100   # negativ = adverse
  MFE = max(high during trade) - 100  # positiv = favorable

Short-Position (Entry=100, Exit=95):
  MAE = 100 - max(high during trade)  # adverse move = Price up
  MFE = 100 - min(low during trade)   # favorable move = Price down
```

**Dollar-Units:**
```
mae_dollars = mae_price * quantity
mfe_dollars = mfe_price * quantity
```

**Fallback-Chain-Pattern:**
```python
async def get_candles(symbol, start, end, timeframe):
    for client in [ib_client, binance_client, kraken_client, mcp_client]:
        try:
            return await asyncio.wait_for(
                client.get_candles(symbol, start, end, timeframe),
                timeout=15.0
            )
        except (ConnectionError, asyncio.TimeoutError):
            continue
    return None  # Graceful degradation
```

**File Structure:**
```
migrations/
└── 004_ohlc_candles_table.sql      # NEW
app/
├── models/
│   └── ohlc.py                      # NEW
├── clients/
│   ├── ohlc/
│   │   ├── __init__.py              # NEW
│   │   ├── base.py                  # NEW - Protocol
│   │   ├── ib_historical.py         # NEW
│   │   ├── binance.py               # NEW
│   │   └── kraken.py                # NEW
└── services/
    ├── ohlc_cache.py                # NEW
    └── mae_mfe.py                   # NEW
```

### References

- PRD: FR13a, NFR-I6
- Architecture: "OHLC Candle Cache", "Intraday Candle Data"
- Concern m3 aus Readiness-Report: ohlc_candles Migration jetzt explizit in AC 2

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
