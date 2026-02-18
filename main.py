#!/usr/bin/env python3
"""
Kitbash FastAPI HTTP Service

Phase 3C: Turn QueryOrchestrator into a callable HTTP service.

Endpoints:
  POST   /api/query         - Single query
  POST   /api/batch_query   - Multiple queries
  GET    /health            - Service health check
  GET    /info              - Service information & stats

Usage:
  uvicorn main:app --host 0.0.0.0 --port 8000
  or
  python main.py (runs on localhost:8000)
"""

import sys
import time
import logging
import types
import importlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# --- Path setup: Map 'kitbash' namespace to local directories ---
SRC_DIR = Path(__file__).resolve().parent / "src"
ROOT_DIR = Path(__file__).resolve().parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Patch the 'kitbash' namespace
if "kitbash" not in sys.modules:
    kitbash_mod = types.ModuleType("kitbash")
    kitbash_mod.__path__ = [str(SRC_DIR), str(ROOT_DIR)]
    sys.modules["kitbash"] = kitbash_mod

mapping = {
    "interfaces": SRC_DIR / "interfaces",
    "engines": SRC_DIR / "engines",
    "orchestration": SRC_DIR / "orchestration",
    "memory": SRC_DIR / "memory",
    "context": SRC_DIR / "context",
    "routing": SRC_DIR / "routing",
    "metabolism": ROOT_DIR / "metabolism"
}

for sub, path in mapping.items():
    full_name = f"kitbash.{sub}"
    try:
        if path.exists() and full_name not in sys.modules:
            parent_str = str(path.parent)
            if parent_str not in sys.path:
                sys.path.insert(0, parent_str)
            mod = importlib.import_module(sub)
            sys.modules[full_name] = mod
    except Exception as e:
        print(f"Warning: Failed to import kitbash.{sub}: {e}")

# --- Now import from kitbash ---
from kitbash.orchestration.query_orchestrator import QueryOrchestrator, QueryResult, LayerAttempt
from kitbash.routing.rule_based_triage import RuleBasedTriageAgent
from kitbash.engines.grain_engine import GrainEngine
from kitbash.engines.cartridge_engine import CartridgeEngine
from kitbash.context.mock_mamba_service import MockMambaService
from kitbash.memory.resonance_weights import ResonanceWeightService
from kitbash.metabolism.heartbeat_service import HeartbeatService
from kitbash.metabolism.metabolism_scheduler import MetabolismScheduler
from kitbash.metabolism.background_metabolism_cycle import BackgroundMetabolismCycle

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Request/Response models for FastAPI ---

class QueryRequest(BaseModel):
    """Single query request."""
    query: str = Field(..., description="The user's question")
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional context (session_id, user_id, etc.)"
    )


class BatchQueryRequest(BaseModel):
    """Multiple queries request."""
    queries: List[Dict[str, Any]] = Field(
        ...,
        description="List of queries, each with 'query' and optional 'context'"
    )


class LayerAttemptResponse(BaseModel):
    """Response model for a single layer attempt."""
    engine_name: str
    confidence: float
    threshold: float
    passed: bool
    latency_ms: float
    error: Optional[str] = None


class QueryResponseModel(BaseModel):
    """Single query response."""
    query_id: str
    answer: Optional[str]
    confidence: float
    engine_name: str
    triage_reasoning: str
    total_latency_ms: float
    layer_results: List[LayerAttemptResponse]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    uptime_seconds: float
    engines_available: List[str]
    cartridges_loaded: int
    grain_count: int


class InfoResponse(BaseModel):
    """Service info response."""
    version: str
    service_name: str
    description: str
    engines: List[str]
    cartridges: int
    grain_count: int
    metrics: Dict[str, Any]


# --- Global orchestrator instance ---
_orchestrator: Optional[QueryOrchestrator] = None
_startup_time: float = time.time()


def _initialize_orchestrator() -> QueryOrchestrator:
    """Initialize the QueryOrchestrator with all components."""
    global _orchestrator

    if _orchestrator is not None:
        return _orchestrator

    logger.info("Initializing QueryOrchestrator...")

    try:
        # Initialize components
        triage_agent = RuleBasedTriageAgent()
        grain_engine = GrainEngine()
        cartridge_engine = CartridgeEngine(cartridges_dir=str(SRC_DIR / "cartridges"))
        mamba_service = MockMambaService()
        resonance = ResonanceWeightService()
        heartbeat = HeartbeatService(initial_turn=0)

        # Initialize background metabolism cycle and scheduler
        bg_cycle = BackgroundMetabolismCycle(triage_agent, resonance)
        metabolism_scheduler = MetabolismScheduler(bg_cycle, heartbeat, background_interval=100)

        # Build engines dict
        engines = {
            "GRAIN": grain_engine,
            "CARTRIDGE": cartridge_engine,
        }

        # Create orchestrator
        _orchestrator = QueryOrchestrator(
            triage_agent=triage_agent,
            engines=engines,
            mamba_service=mamba_service,
            resonance=resonance,
            heartbeat=heartbeat,
            metabolism_scheduler=metabolism_scheduler,
            shannon=None,
            diagnostic_feed=None,
        )

        logger.info("QueryOrchestrator initialized successfully")
        return _orchestrator

    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}", exc_info=True)
        raise


# --- FastAPI app ---
app = FastAPI(
    title="Kitbash Knowledge Orchestration API",
    description="Phase 3C MVP - Turn QueryOrchestrator into a callable HTTP service",
    version="0.1.0",
)


@app.on_event("startup")
async def startup_event():
    """Initialize orchestrator on startup."""
    try:
        _initialize_orchestrator()
        logger.info("FastAPI startup complete")
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise


# --- Endpoints ---

@app.post("/api/query", response_model=QueryResponseModel)
async def api_query(request: QueryRequest) -> QueryResponseModel:
    """
    Process a single query through the orchestrator.

    Returns the answer, confidence, which engine responded, and timing details.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if len(request.query) > 2000:
        raise HTTPException(status_code=400, detail="Query too long (max 2000 characters)")

    try:
        context = request.context or {}
        result: QueryResult = _orchestrator.process_query(request.query, context)

        # Convert dataclass to dict and build response
        layer_results = [
            LayerAttemptResponse(**asdict(attempt))
            for attempt in result.layer_results
        ]

        return QueryResponseModel(
            query_id=result.query_id,
            answer=result.answer,
            confidence=result.confidence,
            engine_name=result.engine_name,
            triage_reasoning=result.triage_reasoning,
            total_latency_ms=result.total_latency_ms,
            layer_results=layer_results,
        )

    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@app.post("/api/batch_query")
async def api_batch_query(request: BatchQueryRequest) -> Dict[str, Any]:
    """
    Process multiple queries in sequence.

    Returns a list of results matching the input query order.
    """
    if not request.queries:
        raise HTTPException(status_code=400, detail="Queries list cannot be empty")

    if len(request.queries) > 100:
        raise HTTPException(status_code=400, detail="Too many queries (max 100)")

    results = []

    for idx, query_obj in enumerate(request.queries):
        try:
            if isinstance(query_obj, str):
                query_text = query_obj
                context = {}
            elif isinstance(query_obj, dict):
                query_text = query_obj.get("query")
                context = query_obj.get("context", {})
            else:
                results.append({
                    "index": idx,
                    "error": "Invalid query format"
                })
                continue

            if not query_text:
                results.append({
                    "index": idx,
                    "error": "Query text is empty"
                })
                continue

            # Process query
            result: QueryResult = _orchestrator.process_query(query_text, context)

            layer_results = [
                asdict(attempt)
                for attempt in result.layer_results
            ]

            results.append({
                "index": idx,
                "query_id": result.query_id,
                "answer": result.answer,
                "confidence": result.confidence,
                "engine_name": result.engine_name,
                "total_latency_ms": result.total_latency_ms,
                "layer_results": layer_results,
            })

        except Exception as e:
            logger.error(f"Batch query {idx} failed: {e}", exc_info=True)
            results.append({
                "index": idx,
                "error": str(e)
            })

    return {"results": results, "total": len(results), "succeeded": len([r for r in results if "error" not in r])}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Check service health."""
    try:
        uptime = time.time() - _startup_time

        engines_available = list(_orchestrator.engines.keys()) if _orchestrator else []

        # Try to get cartridge and grain stats
        cartridges_loaded = 0
        grain_count = 0

        try:
            if _orchestrator and hasattr(_orchestrator.engines.get("GRAIN"), "cartridge_manager"):
                grain_engine = _orchestrator.engines["GRAIN"]
                if hasattr(grain_engine, "grains"):
                    grain_count = len(grain_engine.grains)

            if _orchestrator and hasattr(_orchestrator.engines.get("CARTRIDGE"), "cartridges"):
                cartridge_engine = _orchestrator.engines["CARTRIDGE"]
                cartridges_loaded = len(cartridge_engine.cartridges)
        except Exception as e:
            logger.warning(f"Failed to get cartridge/grain stats: {e}")

        return HealthResponse(
            status="healthy",
            uptime_seconds=uptime,
            engines_available=engines_available,
            cartridges_loaded=cartridges_loaded,
            grain_count=grain_count,
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@app.get("/info", response_model=InfoResponse)
async def info() -> InfoResponse:
    """Get service information and statistics."""
    try:
        metrics = _orchestrator.get_metrics() if _orchestrator else {}

        engines_available = list(_orchestrator.engines.keys()) if _orchestrator else []

        # Get cartridge/grain counts
        cartridges_loaded = 0
        grain_count = 0

        try:
            if _orchestrator and hasattr(_orchestrator.engines.get("GRAIN"), "grains"):
                grain_engine = _orchestrator.engines["GRAIN"]
                grain_count = len(grain_engine.grains)

            if _orchestrator and hasattr(_orchestrator.engines.get("CARTRIDGE"), "cartridges"):
                cartridge_engine = _orchestrator.engines["CARTRIDGE"]
                cartridges_loaded = len(cartridge_engine.cartridges)
        except Exception as e:
            logger.warning(f"Failed to get cartridge/grain stats: {e}")

        return InfoResponse(
            version="0.1.0",
            service_name="Kitbash Knowledge Orchestration",
            description="Phase 3C MVP - HTTP wrapper for QueryOrchestrator",
            engines=engines_available,
            cartridges=cartridges_loaded,
            grain_count=grain_count,
            metrics=metrics,
        )

    except Exception as e:
        logger.error(f"Info request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Info request failed: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint - redirects to docs."""
    return {
        "message": "Kitbash Knowledge Orchestration API",
        "version": "0.1.0",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Kitbash FastAPI server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
