# Story 13.1: Cashflow-per-Period-Chart (Reingewinne Tag/Woche/Monat/Jahr)

Status: ready-for-dev (pending chef-approval)

## Story

As a Chef,
I want a chart that shows my net realized trade profits per day, week, month, and year (with a period toggle),
so that I can see at a glance whether I made money in a given time window — without account deposits/withdrawals polluting the picture.

## Kontext

Chef-Feedback 2026-04-24: *"Es werden pro Tag/Woche/Monat/Jahr die Reingewinne (ohne Ein- und Auszahlungen) ermittelt."* Das ist die Kern-View, die visualtradingjournal.com besser löst als unser aktuelles Journal.

"Reingewinne" = **Summe der `pnl`-Werte aus geschlossenen Trades**, gruppiert nach `DATE_TRUNC(period, closed_at)`. Einzahlungen / Auszahlungen werden von ctrader nicht modelliert (out-of-scope MVP), also automatisch excluded — wir aggregieren ausschließlich Trade-P&L.

## Acceptance Criteria

1. **Given** geschlossene Trades in der DB, **When** `/journal` geladen wird, **Then** erscheint oberhalb der Trade-Liste und *statt* der bisherigen 4 identischen Sparkline-Hero-Cards ein **Cashflow-Chart** (Balken pro Periode, grün für positive Perioden, rot für negative) mit einem **Period-Toggle** `Tag | Woche | Monat | Jahr` (Default: `Monat`).

2. **Given** der Chart ist sichtbar, **When** Chef den Period-Toggle umschaltet, **Then** aktualisiert sich der Chart **ohne Full-Page-Reload** via HTMX (Pattern analog zu `_parse_facet_query` in Epic 4), und die aktive Periode ist in der URL als `?period=day|week|month|year` bookmarkable.

3. **Given** Facetten-Filter sind aktiv (z.B. `broker=ib`, `strategy=swing_long`), **When** der Cashflow-Chart rendert, **Then** berücksichtigt die Aggregation *dieselben* Filter wie die Trade-Liste (einheitlicher `build_where_clause`-Pfad aus Epic 4).

4. **Given** der Chart rendert, **When** Chef über einen Balken hovert, **Then** zeigt ein Tooltip: Perioden-Label (`"2026-03"` / `"KW 14/2026"` / `"2026-03-18"` / `"2026"`), Brutto-P&L (Summe aus `pnl`), Anzahl Trades, und — *nur bei period=day* — eine klickbare "→ Trades dieses Tages"-Verlinkung auf die bestehende `/journal/calendar/<YYYY-MM-DD>`-Route.

5. **Given** keine geschlossenen Trades im Zeitfenster existieren, **When** der Chart rendert, **Then** zeigt er einen Empty-State `"Keine geschlossenen Trades für diesen Filter"` — kein leerer Chart-Canvas, keine Fehlermeldung.

6. **Given** ≤2000 geschlossene Trades, **When** die Aggregation läuft, **Then** liefert der Endpoint das Ergebnis innerhalb von **500 ms** (strenger als NFR-P4 weil rein SQL-seitig aggregiert, keine Python-Schleife).

7. **Given** Trades mit `pnl=NULL` (z.B. offene Trades die versehentlich im Filter landen), **When** die Aggregation läuft, **Then** werden diese **ausgeschlossen** (`WHERE status='closed' AND pnl IS NOT NULL`) — nicht als 0 gezählt, nicht als NULL addiert.

8. **Given** der Chart rendert, **When** in UTC vs. CET verschiedene Kalender-Tage betroffen sind, **Then** wird der Buckt-Schlüssel **via der Chef-Zeitzone `Europe/Zurich`** berechnet (`DATE_TRUNC(period, closed_at AT TIME ZONE 'Europe/Zurich')`) — ein Trade, geschlossen am 2026-03-18 23:30 UTC, landet korrekt im CET-Tages-Bucket des 2026-03-19. Dokumentiert + getestet. (Löst pre-existing D84 *en passant* für diese View.)

9. **Given** `period=year`, **When** Chef ≥2 Jahre Trade-Historie hat, **Then** sind die Jahres-Balken absteigend-chronologisch sortiert (aktuellstes Jahr rechts), und die Y-Achse skaliert proportional zu `max(|pnl_pro_jahr|)`.

10. **Given** der Chart rendert, **When** Chef unterhalb des Charts eine Kennziffer-Zeile sehen möchte, **Then** erscheint eine Zusammenfassung: `Σ P&L: CHF X · Positive Perioden: N/M (X%) · Beste Periode: <Label> (+Y) · Schlechteste: <Label> (-Z)`. Kein separates Panel, nur eine Zeile.

## Tasks / Subtasks

- [ ] **Task 1: Service-Funktion `cashflow_per_period()`** (AC: 1, 3, 6, 7, 8)
  - [ ] 1.1 Neue Datei `app/services/analytics.py`
  - [ ] 1.2 Signatur: `async def cashflow_per_period(conn, period: Literal['day','week','month','year'], filters: FacetFilters) -> CashflowResult`
  - [ ] 1.3 SQL-Query (Entwurf, siehe Dev Notes)
  - [ ] 1.4 Reuse `build_where_clause()` aus `app/services/facets/registry.py` für Filter-Konsistenz
  - [ ] 1.5 Return Type: Pydantic-Modell `CashflowResult { buckets: list[CashflowBucket], summary: CashflowSummary }`

- [ ] **Task 2: Route + HTMX-Fragment** (AC: 2, 5)
  - [ ] 2.1 `GET /analytics/cashflow` — gibt HTML-Fragment mit `<div>` + Chart-Canvas + Summary-Zeile zurück
  - [ ] 2.2 Query-Params: `period`, plus alle bestehenden Facetten-Params
  - [ ] 2.3 HTMX-Attribute auf dem Toggle: `hx-get="/analytics/cashflow?period=..."`, `hx-target="#cashflow-chart"`, `hx-push-url="true"`
  - [ ] 2.4 Empty-State wenn `buckets == []`

- [ ] **Task 3: Chart-Component** (AC: 1, 4, 9)
  - [ ] 3.1 Neue Fragment-Datei `app/templates/fragments/cashflow_chart.html`
  - [ ] 3.2 Nutzt `lightweight-charts` (Locked Decision) mit `HistogramSeries` (grün/rot)
  - [ ] 3.3 Tooltip: Period-Label + P&L + Trade-Count; bei period=day zusätzlich Anchor-Link
  - [ ] 3.4 Period-Toggle als `<button>`-Gruppe mit `aria-pressed`
  - [ ] 3.5 Summary-Zeile unterhalb (siehe AC #10)

- [ ] **Task 4: Integration in `/journal`** (AC: 1)
  - [ ] 4.1 `app/templates/pages/journal.html` — 4er-Sparkline-Grid (Zeile 31-41) durch `{% include "fragments/cashflow_chart.html" %}` ersetzen
  - [ ] 4.2 Nicht entfernen: Trade-Count, Expectancy, Winrate, Drawdown — die wandern als kompakte Chips oberhalb des Charts
  - [ ] 4.3 Backwards-Compat: bei `?period` nicht gesetzt → Default `month` + URL-Push

- [ ] **Task 5: Zeitzone-Robustheit** (AC: 8)
  - [ ] 5.1 SQL nutzt `closed_at AT TIME ZONE 'Europe/Zurich'`
  - [ ] 5.2 Settings-Override: `settings.display_timezone` (Default `"Europe/Zurich"`) — falls Chef je nach Jet-Lag umschaltet
  - [ ] 5.3 Unit-Test: Trade mit `closed_at='2026-03-18 23:30 UTC'` landet im `2026-03-19`-Tages-Bucket

- [ ] **Task 6: Tests** (AC: alle)
  - [ ] 6.1 Unit: `cashflow_per_period` mit leerer DB → leere Result-Liste
  - [ ] 6.2 Unit: nur offene Trades → leere Result-Liste (AC #7)
  - [ ] 6.3 Unit: gemischte P&L-Vorzeichen über 3 Monate → korrekte Bucket-Summen
  - [ ] 6.4 Unit: Facetten-Filter (z.B. `broker=ib`) wirkt sich auf Aggregation aus (AC #3)
  - [ ] 6.5 Unit: Zeitzone-Edge-Case (AC #8)
  - [ ] 6.6 Integration: `GET /analytics/cashflow?period=month` via TestClient → HTML-Fragment mit erwartetem Chart-Canvas-Placeholder
  - [ ] 6.7 Performance: 2000-Trade-Fixture → `cashflow_per_period(period='day')` < 500 ms (AC #6)

- [ ] **Task 7: Docs-Update**
  - [ ] 7.1 `docs/analytics.md` (neu) — dokumentiert den Cashflow-Endpoint, Perioden-Semantik, Known Limitation Currency
  - [ ] 7.2 `README.md` — Screenshot oder Link zu `/journal` mit Cashflow-Chart

## Dev Notes

### SQL-Entwurf (PostgreSQL)

```sql
-- period: 'day' | 'week' | 'month' | 'year'
-- tz: 'Europe/Zurich'
WITH filtered AS (
    SELECT
        pnl,
        closed_at,
        fees
    FROM trades
    WHERE closed_at IS NOT NULL
      AND pnl IS NOT NULL
      {facet_conditions}   -- via build_where_clause()
)
SELECT
    DATE_TRUNC($1, closed_at AT TIME ZONE $2) AS bucket,
    SUM(pnl)                                    AS net_pnl,
    SUM(fees)                                   AS total_fees,
    COUNT(*)                                    AS trade_count
FROM filtered
GROUP BY bucket
ORDER BY bucket ASC;
```

Performance-Anmerkung: `idx_trades_opened_at` existiert (Migration 002), aber **kein Index auf `closed_at`**. Bei >50k Trades wird das zu einem Full-Scan. Kann mit einem partiellen Index gelöst werden:

```sql
-- Optional (Task 6.7 Performance-Fallback, nicht Pflicht für MVP):
CREATE INDEX IF NOT EXISTS idx_trades_closed_at
    ON trades (closed_at) WHERE closed_at IS NOT NULL;
```

Das wäre eine **eigene Migration 020** — nur anlegen, wenn die 2000-Trade-Perf-Test das 500-ms-SLA reißt.

### Chart-Bibliothek

`lightweight-charts` (Locked Decision, Apache 2.0, bereits über Story 4.5 verdrahtet). `HistogramSeries` kennt Farb-per-Bar via `color`-Property:

```javascript
const histogramSeries = chart.addHistogramSeries({
  priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
});
histogramSeries.setData(buckets.map(b => ({
  time: b.bucket_iso,
  value: parseFloat(b.net_pnl),
  color: parseFloat(b.net_pnl) >= 0 ? '#10b981' : '#ef4444',
})));
```

### Datenmodell-Impact

**Keiner.** Kein `ALTER TABLE`, keine neue Tabelle, keine neue Migration (außer Task 6.7 optional). Alle Daten aus `trades.pnl` + `trades.closed_at` + bestehende Facetten-Where-Klausel.

### Known Limitation: Currency

`trades.pnl` ist `NUMERIC` ohne Einheit. Bei Multi-Currency-Konten addiert der Chart Äpfel und Birnen. Heute folgenlos (nur IB-USD). Der Fix ist eine separate Story in einem zukünftigen Epic 14 — **nicht Teil von 13.1**. Ich dokumentiere die Limitation in `docs/analytics.md` (Task 7.1) plus einen Hinweis-Banner am Chart, sobald Trades mit mehreren `broker`-Werten im Filter enthalten sind:

```
⚠ Multi-Broker-Ansicht: Die Summe addiert P&L ohne Währungsumrechnung. Filtere auf einen Broker für akkurate Beträge.
```

### Reihenfolgen-Hinweis zu D69 (Expectancy-in-R)

Die 4 bisherigen Hero-Cards (Trade-Count, Expectancy, Winrate, Drawdown) wandern als Chips in die Kopfzeile über dem Chart. Das schließt D69 (Dollar-Expectancy → R-Expectancy) **nicht** ab — das bleibt als separater Fix. Aber: bei Implementierung von 13.1 bitte die Chip-Implementierung so schreiben, dass der Wert-Renderer austauschbar ist, damit D69 später nur einen Aufruf wechselt.

### Verwandte Reviews

- Aggregation-Cache (D72) — bei Implementation prüfen, ob der Facet-Cache greift, sonst separate TTLCache für `cashflow_per_period`.
- Zeitzone-Konsistenz (D84 Calendar) — 13.1 löst das für diese View; Calendar bleibt weiter UTC-bucketed bis eigener Fix.

## Definition of Done

- [ ] Alle 10 Acceptance Criteria erfüllt + je min. ein Test
- [ ] Chart sichtbar auf `/journal` nach Login (oder direkt, da Single-User-Localhost)
- [ ] Manuelle Smoke-Probe mit echten IB-Flex-Daten (≥1 Monat Historie): Chef kann die drei Erfolgskriterien aus Epic 13 Zeile "Erfolgskriterium" live beantworten
- [ ] `pytest -m "not integration"` grün; `pytest -m integration` mit Testcontainer grün
- [ ] `ruff check .` grün
- [ ] Commit + Push gemäß CLAUDE.md Regel 1
