/* Placeholder for lightweight-charts.standalone.production.js
 *
 * Story 4.5 ships the integration surface (chart_data endpoint +
 * drilldown container + client-side initialisation code) but the
 * actual 35KB TradingView library file is NOT bundled in this
 * repository — Chef can drop it in manually from
 * https://github.com/tradingview/lightweight-charts/releases
 * or via CDN when the chart is actually needed.
 *
 * Without the real library, window.LightweightCharts stays
 * undefined and the drilldown chart container renders its
 * "Chart-Library nicht geladen" placeholder — graceful degradation
 * instead of a JS error.
 */
