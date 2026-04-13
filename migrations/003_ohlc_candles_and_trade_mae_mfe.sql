-- 003_ohlc_candles_and_trade_mae_mfe.sql
--
-- Story 4.3: MAE/MFE calculation + OHLC candle cache.
--
-- 1. `ohlc_candles` — cache of intraday candle data keyed on
--    (symbol, timeframe, ts). 24h TTL at read-time via
--    `cached_at > NOW() - INTERVAL '24 hours'`.
-- 2. `trades.mae_price` / `trades.mfe_price` / their dollar
--    counterparts — per-trade Maximum Adverse / Favorable Excursion.
--    NULL until the first cache hit produces real data; the
--    drilldown template renders "—" for NULLs (graceful degradation).
--
-- Story 4.5's OHLC chart reads from the same `ohlc_candles` cache.

-- ---------------------------------------------------------------------
-- OHLC candle cache
-- ---------------------------------------------------------------------

-- Timeframe enum: we only need two bar widths for MAE/MFE today.
-- Additional timeframes (`15m`, `1h`, `1d`) land when the daily chart
-- story (post-Epic-4) needs them.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ohlc_timeframe') THEN
        CREATE TYPE ohlc_timeframe AS ENUM ('1m', '5m');
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS ohlc_candles (
    id          SERIAL          PRIMARY KEY,
    symbol      TEXT            NOT NULL,
    timeframe   ohlc_timeframe  NOT NULL,
    ts          TIMESTAMPTZ     NOT NULL,
    open        NUMERIC         NOT NULL,
    high        NUMERIC         NOT NULL,
    low         NUMERIC         NOT NULL,
    close       NUMERIC         NOT NULL,
    volume      NUMERIC,
    cached_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, timeframe, ts)
);

CREATE INDEX IF NOT EXISTS idx_ohlc_candles_symbol_ts
    ON ohlc_candles (symbol, timeframe, ts);

-- ---------------------------------------------------------------------
-- trades.mae_* / mfe_* columns
-- ---------------------------------------------------------------------

ALTER TABLE trades
    ADD COLUMN IF NOT EXISTS mae_price   NUMERIC,
    ADD COLUMN IF NOT EXISTS mfe_price   NUMERIC,
    ADD COLUMN IF NOT EXISTS mae_dollars NUMERIC,
    ADD COLUMN IF NOT EXISTS mfe_dollars NUMERIC,
    ADD COLUMN IF NOT EXISTS mae_mfe_computed_at TIMESTAMPTZ;
