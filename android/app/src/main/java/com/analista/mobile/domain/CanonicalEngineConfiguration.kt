package com.analista.mobile.domain

import com.analista.mobile.data.NormalizedDatasetCodec
import com.analista.mobile.data.ProviderMatrixPolicy
import com.analista.mobile.data.RunDatasetCaptureService
import com.analista.mobile.data.RunUniverseRegistry
import com.analista.mobile.data.UniverseObservationRegistry
import com.analista.mobile.data.YahooFinanceClient
import com.analista.mobile.data.YahooOptionChainParser
import java.util.Locale

object CanonicalEngineConfiguration {
    const val VERSION = "canonical-engine-config-1"

    fun create(
        policyVersion: String,
        riskPct: Double,
        maxPositionPct: Double,
        minRiskReward: Double,
        minStopAtr: Double,
        targetSessions: Int
    ): Map<String, String> = sortedMapOf(
        // Product contract
        "configurationContractVersion" to VERSION,
        "policyVersion" to policyVersion,
        "strategyDirection" to "LONG_ONLY",
        "minimumHorizonSessions" to "4",
        "maximumHorizonSessions" to "21",
        "executionMode" to "MANUAL_REVIEW",
        "portfolioConstructionEnabled" to "false",
        "buySetupActiveEnabled" to "false",

        // Universe and hard filters
        "universeMode" to UniverseSelectionEngine.MODE,
        "minimumPrice" to canonical(TradingPolicy.MIN_PRICE),
        "minimumMarketCapUsd" to TradingPolicy.MIN_MARKET_CAP.toString(),
        "minimumUniverseDollarVolume" to canonical(UniverseSelectionEngine.MIN_AVERAGE_DOLLAR_VOLUME),
        "maximumUniverseSpreadPct" to canonical(UniverseSelectionEngine.MAX_SPREAD_PCT),
        "excludedQuoteTypes" to TradingPolicy.excludedQuoteTypes.sorted().joinToString(","),
        "universeSelectionVersion" to UniverseSelectionEngine.VERSION,
        "liveUniverseAssemblerVersion" to LiveUniverseSnapshotAssembler.VERSION,
        "runUniverseRegistryVersion" to RunUniverseRegistry.VERSION,
        "universeObservationRegistryVersion" to UniverseObservationRegistry.VERSION,

        // Market data and execution quote
        "maximumQuoteDistancePct" to canonical(TradingPolicy.MAX_QUOTE_DISTANCE_PCT),
        "maximumTightQuoteSpreadPct" to canonical(1.0),
        "quoteFreshSeconds" to "120",
        "quoteDelayedAcceptableSeconds" to "900",
        "quoteMaximumFutureSkewSeconds" to "30",
        "quoteFreshnessVersion" to QuoteFreshnessEngine.VERSION,
        "providerMatrixVersion" to ProviderMatrixPolicy.VERSION,
        "historicalPriceProviderPrimary" to "ALPACA_WHEN_AVAILABLE",
        "historicalPriceProviderFallback" to "YAHOO",
        "executionQuoteProviderPrimary" to "ALPACA",
        "executionQuoteProviderFallback" to "YAHOO",
        "fundamentalProviderPrimary" to "YAHOO",
        "fundamentalProviderFallbackOrder" to "FINVIZ,MARKETWATCH,TRADINGVIEW",
        "optionsProviderPrimary" to "BEST_AVAILABLE_ADAPTER",
        "optionsProviderFallback" to "YAHOO",
        "macroProviderPrimary" to "YAHOO",
        "calendarProvider" to "LOCAL_VERSIONED_NYSE",

        // Canonical technical indicators and warm-up
        "minimumHistoryBars" to "60",
        "smaFastPeriod" to "20",
        "smaSlowPeriod" to "50",
        "emaFastPeriod" to "20",
        "emaMediumPeriod" to "50",
        "emaLongPeriod" to "200",
        "emaSeed" to "SMA",
        "rsiFastPeriod" to "6",
        "rsiCanonicalPeriod" to "14",
        "rsiSmoothing" to "WILDER",
        "atrPeriod" to "14",
        "atrSmoothing" to "WILDER",
        "macdFastPeriod" to "12",
        "macdSlowPeriod" to "26",
        "macdSignalPeriod" to "9",
        "stochasticPeriod" to "14",
        "relativeVolumePeriod" to "20",
        "indicatorWarmupRule" to "PERIOD_SMA_SEED_AND_VALID_OUTPUT_ONLY",
        "canonicalAnalysisVersion" to CanonicalAnalysisEngine.ENGINE_VERSION,

        // Legacy technical score retained for shadow comparison
        "legacyWeightPriceAboveSma20" to "15",
        "legacyWeightSma20AboveSma50" to "20",
        "legacyWeightRsiConstructive" to "15",
        "legacyWeightMacdBullish" to "15",
        "legacyWeightStochasticConfirmed" to "10",
        "legacyWeightRelativeVolume" to "15",
        "legacyWeightLiveBreakout" to "10",
        "legacyRsiConstructiveMin" to canonical(50.0),
        "legacyRsiConstructiveMax" to canonical(70.0),
        "legacyStochasticMin" to canonical(35.0),
        "legacyStochasticMax" to canonical(80.0),
        "legacyRelativeVolumeMinimum" to canonical(1.2),
        "overextensionRsiThreshold" to canonical(75.0),
        "overextensionDistanceAtr" to canonical(2.5),

        // Breakout, trigger and setup rules
        "breakoutLookbackSessions" to "20",
        "breakoutBufferAtr" to canonical(0.25),
        "breakoutBufferPct" to canonical(0.5),
        "maximumEntryAtrAboveTrigger" to canonical(0.5),
        "maximumOpeningGapAtr" to canonical(1.5),
        "setupConstructiveRsiMin" to canonical(45.0),
        "setupConstructiveRsiMax" to canonical(70.0),
        "setupRetestMaximumDistanceAtr" to canonical(0.35),
        "setupPullbackMaximumDistanceAtr" to canonical(0.5),
        "setupCompressionMaximumRatio" to canonical(0.70),
        "setupStrongCompressionRatio" to canonical(0.60),
        "setupConfirmationIncrement" to canonical(7.0),
        "setupClassifierVersion" to SetupClassificationEngine.VERSION,

        // Structure, stop, target and sizing
        "riskPct" to canonical(riskPct),
        "maxPositionPct" to canonical(maxPositionPct),
        "minRiskReward" to canonical(minRiskReward),
        "minStopAtr" to canonical(minStopAtr),
        "preferredStopAtrMin" to canonical(1.0),
        "preferredStopAtrMax" to canonical(2.5),
        "aggressiveStopMaximumAtr" to canonical(1.0),
        "aggressiveStopMinimumRiskReward" to canonical(3.0),
        "aggressiveStopMinimumStructureScore" to canonical(80.0),
        "aggressiveStopMinimumSetupScore" to canonical(75.0),
        "defaultAtrStopMultiple" to canonical(1.5),
        "defaultTargetRiskMultiple" to canonical(2.5),
        "targetSessions" to targetSessions.toString(),
        "structureRiskVersion" to StructureRiskEngine.VERSION,
        "aggressiveStopPolicyVersion" to AggressiveStopPolicy.VERSION,
        "tradePlanVersion" to TradePlanGenerationEngine.ENGINE_VERSION,

        // Macro, fundamental and institutional engines
        "macroHorizonsSessions" to "1,20,60",
        "macroMinimumHighConfidenceInputs" to "6",
        "macroRegimeVersion" to MacroRegimeEngine.VERSION,
        "fundamentalCoverageStates" to "COMPLETE,PARTIAL,STALE,EMPTY,ERROR",
        "fundamentalEarningsRiskMode" to "STRONG_DEGRADATION_NOT_UNIVERSAL_VETO",
        "fundamentalAssessmentVersion" to FundamentalAssessmentEngine.VERSION,
        "optionNearSpotWindowPct" to canonical(10.0),
        "optionExpiryLimit" to YahooFinanceClient.MAX_OPTION_EXPIRIES.toString(),
        "optionChainParserVersion" to YahooOptionChainParser.VERSION,
        "optionMetricsVersion" to OptionMetricsEngine.VERSION,
        "optionAssessmentPersistenceVersion" to OptionAssessmentPersistenceFactory.VERSION,
        "institutionalContrarianVersion" to InstitutionalContrarianEngine.VERSION,
        "institutionalHighConflictMaximumSignal" to "WATCHLIST",
        "unknownInstitutionalCoveragePolicy" to "LOWER_CONFIDENCE_SMALL_PENALTY",
        "decisionOverlayVersion" to DecisionOverlayEngine.ENGINE_VERSION,

        // Final decision and contract gating
        "minimumReadyFinalScore" to canonical(65.0),
        "minimumConfirmedFinalScore" to canonical(75.0),
        "confirmedRequiresLiveTrigger" to "true",
        "confirmedRequiresActionableReview" to "true",
        "finalDecisionVersion" to FinalDecisionEngine.VERSION,

        // Backtest assumptions
        "backtestEntrySlippageBps" to canonical(5.0),
        "backtestExitSlippageBps" to canonical(5.0),
        "backtestCommissionPerShare" to canonical(0.0),
        "backtestAmbiguousSameBarPolicy" to "MARK_AMBIGUOUS",
        "backtestGapStopFillPolicy" to "OPEN_WITH_EXIT_SLIPPAGE",
        "backtestGapTargetFillPolicy" to "OPEN_WITH_EXIT_SLIPPAGE",
        "backtestVersion" to BacktestEngine.VERSION,

        // Walk-forward and ranking promotion
        "walkForwardTrainingPct" to canonical(60.0),
        "walkForwardValidationPct" to canonical(20.0),
        "walkForwardTestPct" to canonical(20.0),
        "walkForwardMinimumOutOfSampleClosed" to "100",
        "walkForwardMinimumDominantSetupClosed" to "30",
        "walkForwardMinimumDistinctRegimes" to "2",
        "walkForwardVersion" to WalkForwardStatisticsEngine.VERSION,
        "rankingPromotionTopK" to "5",
        "rankingPromotionMinimumClosedPerRanking" to "100",
        "rankingPromotionMinimumExpectancyImprovementR" to canonical(0.10),
        "rankingPromotionMaximumDrawdownDeteriorationPct" to canonical(10.0),
        "rankingPromotionMinimumDistinctRegimes" to "2",
        "rankingPromotionVersion" to RankingPromotionEngine.VERSION,
        "rankingDefaultMode" to "LEGACY_UNTIL_PROMOTION_GATE",

        // Reproducibility and local dataset storage
        "calendarVersion" to NyseSessionCalendar.VERSION,
        "normalizedDatasetCodecVersion" to NormalizedDatasetCodec.VERSION,
        "liveDatasetCaptureVersion" to RunDatasetCaptureService.VERSION,
        "datasetCompression" to "GZIP",
        "datasetContentAddress" to "SHA-256"
    )

    private fun canonical(value: Double): String = String.format(Locale.US, "%.4f", value)
}
