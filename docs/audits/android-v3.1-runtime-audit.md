# Auditoría de ejecución Android v3.1

La validación física en POCO X7 Pro detectó tres defectos operativos:

1. Metadatos ausentes se interpretaban como incumplimientos confirmados de capitalización o tipo de instrumento.
2. Una ejecución manual fuera de premarket/mercado regular utilizaba quotes stale o cerradas para clasificar estructura y mostrar spread/trigger operativo.
3. El universo productivo seguía siendo la lista fija de megacaps; los snapshots dinámicos sólo versionaban la entrada existente.

Criterios de corrección:

- `marketCap == null` no equivale a `market_cap_below_min`; debe producir `market_cap_unverified` y bloquear contrato sin convertir el activo en VETO.
- `quoteType == null` debe producir `instrument_type_unverified`.
- Sólo PREMARKET y REGULAR pueden validar ejecución. POSTMARKET, CLOSED y UNKNOWN son análisis técnico sin ejecución.
- El setup diario se clasifica desde barras y cierre. La cotización en vivo sólo revalida trigger o ruptura fallida dentro de una sesión ejecutable.
- `NO_VALID_SETUP` significa AVOID, no ineligibilidad del universo.
- VETO queda reservado a incumplimientos confirmados: precio, capitalización conocida por debajo del mínimo o tipo excluido conocido.

Los siguientes PRs deben sustituir la lista fija por Alpaca Assets/Nasdaq y barras Alpaca con fallback Yahoo, integrar fuentes oficiales y reorganizar la interfaz.
