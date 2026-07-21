package com.analista.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.time.LocalDate

class OfficialSourceClientsTest {
    @Before
    fun clearStatus() = SourceStatusRegistry.clear()

    @Test
    fun fredParserSkipsMissingValuesAndSortsDates() {
        val json = """{
          "observations": [
            {"date":"2026-07-18","value":"4.25"},
            {"date":"2026-07-17","value":"."},
            {"date":"2026-07-16","value":"4.20"}
          ]
        }"""
        val series = FredClient().parseSeries("dgs10", json, 100L)
        assertEquals("DGS10", series.seriesId)
        assertEquals(2, series.observations.size)
        assertEquals(LocalDate.of(2026, 7, 16), series.observations.first().date)
        assertEquals(4.25, series.observations.last().value, 0.0001)
    }

    @Test
    fun cboeParserExtractsMarketPutCallRatios() {
        val html = """<table>
          <tr><td>TOTAL PUT/CALL RATIO</td><td>1.00</td></tr>
          <tr><td>INDEX PUT/CALL RATIO</td><td>1.07</td></tr>
          <tr><td>EQUITY PUT/CALL RATIO</td><td>0.66</td></tr>
          <tr><td>CBOE VOLATILITY INDEX (VIX) PUT/CALL RATIO</td><td>0.63</td></tr>
          <tr><td>SPX + SPXW PUT/CALL RATIO</td><td>1.14</td></tr>
        </table>"""
        val ratios = CboeMarketStatisticsClient().parseRatios(html, 100L)
        assertEquals(5, ratios.coverageCount)
        assertEquals(0.66, ratios.equityPutCall ?: 0.0, 0.0001)
        assertEquals(1.14, ratios.spxPutCall ?: 0.0, 0.0001)
    }

    @Test
    fun secParsersReadTickerFactsAndFormFourFilings() {
        val client = SecEdgarClient("Analista test contact@example.com")
        val tickers = client.parseTickerMap(
            """{"0":{"cik_str":1326801,"ticker":"META","title":"Meta Platforms, Inc."}}"""
        )
        assertEquals("0001326801", tickers.single().cik)

        val facts = client.parseCompanyFacts(
            """{"facts":{"us-gaap":{"Revenues":{"units":{"USD":[
              {"val":1000000,"filed":"2026-04-25","end":"2026-03-31","form":"10-Q"}
            ]}}}}}"""
        )
        assertEquals("Revenues", facts.single().concept)
        assertEquals(1_000_000.0, facts.single().value, 0.0)

        val filings = client.parseRecentInsiderFilings(
            """{"filings":{"recent":{
              "form":["10-Q","4"],
              "accessionNumber":["a","b"],
              "filingDate":["2026-05-01","2026-05-02"],
              "reportDate":["2026-03-31","2026-05-01"],
              "primaryDocument":["q.htm","xslF345X05/form4.xml"]
            }}}"""
        )
        assertEquals(1, filings.size)
        assertEquals("4", filings.single().form)
        assertEquals("b", filings.single().accessionNumber)
    }

    @Test
    fun cftcParserComputesInstitutionalNetPositions() {
        val rows = CftcCotClient().parse(
            """[{
              "market_and_exchange_names":"E-MINI S&P 500 - CME",
              "report_date_as_yyyy_mm_dd":"2026-07-14T00:00:00.000",
              "asset_mgr_positions_long_all":"100,000",
              "asset_mgr_positions_short_all":"40,000",
              "lev_money_positions_long_all":"60,000",
              "lev_money_positions_short_all":"90,000",
              "dealer_positions_long_all":"20,000",
              "dealer_positions_short_all":"35,000"
            }]"""
        )
        val row = rows.single()
        assertEquals(60_000L, row.assetManagerNet)
        assertEquals(-30_000L, row.leveragedFundsNet)
    }

    @Test
    fun sourceRegistryAndTradingViewLinkAreDeterministic() {
        SourceStatusRegistry.record(SourceStatus("macro", "fred", "AVAILABLE", "COMPLETE", 100L, "ok"))
        assertEquals("FRED", SourceStatusRegistry.get("MACRO")?.provider)
        assertEquals(1, SourceStatusRegistry.snapshot().size)

        val link = ChartLinks.tradingView("aapl", "nasdaq")
        assertEquals("https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL", link)
        assertTrue(link.startsWith("https://"))
        assertNull(SourceStatusRegistry.get("UNKNOWN"))
    }
}
