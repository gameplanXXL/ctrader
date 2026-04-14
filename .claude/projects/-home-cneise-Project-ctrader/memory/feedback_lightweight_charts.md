---
name: lightweight-charts statt Screenshots
description: Chef hat am 2026-04-12 entschieden, FR13c (Screenshot-Upload) durch dynamische OHLC-Charts via lightweight-charts zu ersetzen
type: feedback
---

Trade-Drilldown zeigt dynamische OHLC-Charts statt statischer Screenshots.

**Why:** Chef will sehen wie der Chart zum Trade-Zeitpunkt aussah — interaktiv mit Zoom/Pan, Entry/Exit-Markern und Indikatoren (SMA, RSI, etc.). Screenshots sind statisch und weniger informativ. TradingView Widgets/iFrames können keine Custom-Marker anzeigen. TradingView Advanced Charts Library ist nicht für Privatpersonen lizenziert. lightweight-charts ist die einzige passende Option (Open-Source, 35KB, kein Node-Build).

**How to apply:** lightweight-charts als lokale JS-Datei in `app/static/js/`. OHLC-Daten von ib_async (Aktien) und Binance/Kraken API (Crypto). Server liefert JSON, Client rendert Chart. FR13c in der Architektur als "Dynamischer Chart" interpretieren, nicht als "Screenshot-Upload". CLAUDE.md ist aktualisiert.
