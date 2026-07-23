from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .context_advisory import ContextAdvisory
from .ingestion import IngestionError, InstitutionalIngestor
from .providers import ProviderPolicy
from .runtime import InstitutionalRuntime, serialize_signal
from .store import InstitutionalStore
from .universe import UniverseBuilder


class RunRequest(BaseModel):
    as_of: datetime | None = None
    refresh: bool = True


class IngestRequest(BaseModel):
    as_of: datetime | None = None
    history_sessions: int = Field(default=320, ge=220, le=1500)
    symbols: list[str] | None = None


def create_app(database_path: str | Path | None = None, api_token: str | None = None) -> FastAPI:
    path = Path(database_path or os.getenv("ANALISTA_INSTITUTIONAL_DB", "cache/institutional.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    store = InstitutionalStore(path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            store.close()

    app = FastAPI(title="Analista Institutional Engine", version="1.81.0", lifespan=lifespan)
    expected_token = api_token if api_token is not None else os.getenv("ANALISTA_API_TOKEN", "")

    def authorize(authorization: str | None = Header(default=None)) -> None:
        if not expected_token:
            raise HTTPException(503, "ANALISTA_API_TOKEN is required for institutional API access")
        supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
        if not supplied or not secrets.compare_digest(supplied, expected_token):
            raise HTTPException(401, "invalid bearer token")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "store_schema": store.SCHEMA_VERSION,
            "provider_contracts": ProviderPolicy.VERSION,
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "store_counts": store.table_counts(),
            "latest_signal_time": store.latest_signal_time(),
        }

    @app.get("/v1/status", dependencies=[Depends(authorize)])
    def status() -> dict[str, object]:
        counts = store.table_counts()
        return {
            "operational": counts["securities"] > 0 and counts["bars"] > 0,
            "store_counts": counts,
            "latest_signal_time": store.latest_signal_time(),
            "latest_runs": store.shadow_runs(limit=10),
            "source_health": store.source_health(),
        }

    @app.post("/v1/ingest/live", dependencies=[Depends(authorize)])
    def ingest_live(request: IngestRequest) -> dict[str, object]:
        try:
            return InstitutionalIngestor(store).ingest_live(
                as_of=request.as_of,
                history_sessions=request.history_sessions,
                symbols=request.symbols,
            ).__dict__
        except IngestionError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/v1/runs", dependencies=[Depends(authorize)])
    def run(request: RunRequest) -> dict[str, object]:
        from config_loader import load_config

        effective_as_of = (request.as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        ingestion = None
        if request.refresh:
            try:
                ingestion = InstitutionalIngestor(store).ingest_live(as_of=effective_as_of).__dict__
            except IngestionError as exc:
                raise HTTPException(503, f"institutional refresh failed; stale fallback prohibited: {exc}") from exc
        runtime_result = InstitutionalRuntime(store, configuration=load_config()).run(effective_as_of)
        context_ingestion = None
        if request.refresh:
            symbols = [signal.symbol for signal in runtime_result.signals]
            context_ingestion = InstitutionalIngestor(store).ingest_context(
                symbols, as_of=effective_as_of
            ).__dict__
        annotated = ContextAdvisory(store).annotate(runtime_result.signals, effective_as_of)
        result = runtime_result.to_dict()
        result["signals"] = [serialize_signal(signal) for signal in annotated]
        result["ingestion"] = ingestion
        result["context_ingestion"] = context_ingestion
        result["selection_policy"] = "TECHNICAL_SETUP_ONLY_CONTEXT_ADVISORY"
        return result

    @app.get("/v1/universe", dependencies=[Depends(authorize)])
    def universe(as_of: datetime = Query(...)) -> dict[str, object]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise HTTPException(400, "as_of must be timezone-aware")
        snapshot = UniverseBuilder(store).build(as_of)
        return {
            "as_of": snapshot.as_of,
            "engine_version": UniverseBuilder.VERSION,
            "funnel": snapshot.funnel,
            "members": [
                {
                    "symbol": row.security.symbol,
                    "asset_type": row.security.asset_type,
                    "sector": row.security.sector,
                    "industry": row.security.industry,
                    "latest_price": row.latest_price,
                    "average_dollar_volume_20d": row.average_dollar_volume_20d,
                    "history_sessions": row.history_sessions,
                }
                for row in snapshot.members
            ],
            "exclusions": [exclusion.__dict__ for exclusion in snapshot.exclusions],
        }

    @app.get("/v1/signals", dependencies=[Depends(authorize)])
    def signals() -> list[dict[str, object]]:
        return [serialize_signal(signal) for signal in store.signals()]

    @app.get("/v1/outcomes", dependencies=[Depends(authorize)])
    def outcomes() -> list[dict[str, object]]:
        return [
            {**outcome.__dict__, "evaluated_at": outcome.evaluated_at.isoformat()}
            for outcome in store.outcomes()
        ]

    @app.get("/v1/source-health", dependencies=[Depends(authorize)])
    def source_health() -> list[dict[str, object]]:
        return store.source_health()

    @app.get("/v1/context", dependencies=[Depends(authorize)])
    def context(as_of: datetime = Query(...), source: str | None = None) -> list[dict[str, object]]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise HTTPException(400, "as_of must be timezone-aware")
        return store.context_as_of(as_of, source)

    app.state.institutional_store = store
    return app


app = create_app()
