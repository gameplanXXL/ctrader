# Epic 13 — Profit-Diagnostik-Dashboard

**Status:** proposed (2026-04-24) · Chef-Freigabe ausstehend
**Scope-Klasse:** Slice-A-Erweiterung (Journal + IB), *kein* Phase-2-Feature
**Voraussichtlicher Umfang:** 4 Stories · ~1–2 Wochen · rein Read-View-Aggregation über bestehende Tabellen

---

## Warum dieses Epic existiert

Chef-Feedback am 2026-04-24: *"Die UX/UI ist aktuell nicht gut. Ich muss besser verstehen, welche Trades profitabel sind. visualtradingjournal.com löst das sehr viel besser."*

Der aktuelle Journal-View (`/journal`) zeigt 4 Hero-Cards (Trades, Expectancy, Winrate, Drawdown) mit **identischer Sparkline** (technischer Zombie: `app/templates/pages/journal.html:35-38` reicht dieselbe `sparkline_svg` viermal durch) plus eine tabellarische Trade-Liste. Für die Frage *"wann verdiene ich Geld, wann nicht"* fehlen:

- **Cashflow-per-Period** — Reingewinne aggregiert nach Tag / Woche / Monat / Jahr (Chef-Prio 1, analog zu visualtradingjournal.com's Cashflow-Analyse)
- **Equity-Kurve + Drawdown-Underwater** — Verlaufsbild statt Punkt-Schätzer
- **R-Multiple-Histogramm, P&L-by-Mistake, P&L-by-Strategy** — Diagnose *welche* Trade-Kategorien tragen oder kosten
- **Winrate-Heatmap + Hold-Duration-Scatter** — zeitliche + strukturelle Muster

Ohne Profit-Diagnostik vor dem 500-k-Live-Ramp hat Chef keine Grundlage, um Strategien gezielt zu verstärken oder stillzulegen. Das Epic ist **Voraussetzung**, nicht Folge, des Live-Gangs.

## Abgrenzung

**In-Scope:**
- Neue Charts auf `/journal` und neuer Seite `/analytics`
- Neue Service-Funktionen in `app/services/analytics.py` (SQL-Aggregation auf `trades`)
- `lightweight-charts` Integration (Locked Decision, bereits in Story 4.5 verdrahtet)

**Out-of-Scope:**
- Kein neues Datenmodell, keine Migration (Aggregationen laufen über bestehende `trades`-Spalten `pnl`, `opened_at`, `closed_at`, `status`, `strategy_id`, `trigger_spec`)
- Kein Live-Monitoring (das ist Epic 11)
- Keine Änderung am IB / cTrader / MCP-Pfad
- Keine Ein-/Auszahlungs-Modellierung (Chef: "ohne Ein- und Auszahlungen" — nur realisiertes Trade-P&L)

## Stories

| Story | Titel | Zentrale Frage, die Chef beantwortet bekommt |
|---|---|---|
| **13.1** | [Cashflow-per-Period-Chart (Tag/Woche/Monat/Jahr)](./../implementation-artifacts/13-1-cashflow-per-period.md) | *Habe ich in Oktober Geld verdient? In Q4 2025? In KW 17?* |
| **13.2** | Equity-Kurve + Drawdown-Underwater auf `/journal` | *Wie ist der Verlauf meiner Performance? Wie tief war meine schlechteste Phase?* |
| **13.3** | Analytics-Seite: R-Multiple-Histogramm + P&L-by-Mistake + P&L-by-Strategy | *Welche Fehler kosten mich am meisten? Welche Strategie trägt?* |
| **13.4** | Winrate-Heatmap (Hour×Weekday) + Hold-Duration×P&L-Scatter | *Bin ich systematisch Montag morgens schlechter? Schließe ich zu früh/spät?* |

**Reihenfolge:** 13.1 zuerst (Chef-Must-Have) → bewerten → 13.2 + 13.3 parallel → 13.4 als Nice-to-have später.

## Requirements-Mapping

Epic 13 bezieht sich auf bestehende PRD-Requirements, ohne neue einzuführen:

- **FR13** ("Chef kann fuer jede Facetten-Kombination eine Aggregation abrufen") — wird durch 13.1/13.3 visuell erweitert
- **FR13b** ("P&L-Kalender-View") — komplementär zum Cashflow-per-Period-Chart (Kalender = Datum-Grid, Cashflow = Balken-Chart über Zeit)
- **FR18b** ("Top-N-Mistakes-Report") — 13.3 wertet das vorhandene Mistake-Report visuell auf
- **NFR-P4** (Aggregation <800ms bei ≤2000 Trades) — gilt für alle neuen Queries

## Known Limitations / Cross-Epic Interaktionen

1. **Keine Currency-Spalte auf `trades`** (Schema 002_trades_table.sql). Alle P&L werden als Zahl ohne Einheit addiert. Solange Chef nur IB-USD-Trades hat, ist das folgenlos. Sobald cTrader (nach Blocker-Abbau) oder Multi-Currency-Konten dazukommen, liefert der Chart falsche Summen. → **Descope-Option:** Chart pro Broker splitten. → **Fix-Pfad:** Eigene Story "Currency-Handling" in Epic 14, nicht hier.
2. **D69 (Expectancy-in-R)** — Epic 4 nutzt Dollar-Expectancy statt R-Multiple. 13.3 macht das R-Multiple-Histogramm sichtbar und wird den Druck auf D69 erhöhen. Kein Blocker.
3. **D143–D145 (Strategy-Metrics-Performance)** — bei >50k Trades wird die In-Python-Aggregation langsam. 13.x-Queries müssen SQL-seitig aggregieren, um das Problem nicht zu vererben.

## Erfolgskriterium des Epics

Chef kann nach Go-Live 13.1 innerhalb von 30 Sekunden die Fragen beantworten:
1. *"Habe ich in den letzten 90 Tagen Geld verdient oder verloren?"*
2. *"War 2026 Q1 besser oder schlechter als Q4 2025?"*
3. *"In welchem Monat hatte ich den größten Rückschlag?"*

Ohne Excel-Export, ohne SQL, ohne Taschenrechner.
