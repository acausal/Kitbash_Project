#!/usr/bin/env python3
"""
Kitbash FastAPI HTTP Service

Phase 3C: Turn QueryOrchestrator into a callable HTTP service.
Phase 3D: Add OpenAI-compatible Chat Completions endpoint for SillyTavern integration.

Endpoints:
  POST   /api/query            - Single query (Kitbash native format)
  POST   /api/batch_query      - Multiple queries
  GET    /health               - Service health check
  GET    /info                 - Service information & stats
  POST   /v1/chat/completions  - OpenAI-compatible Chat Completions (for SillyTavern)
  GET    /v1/models            - List available models (for SillyTavern)

Usage:
  uvicorn main:app --host 0.0.0.0 --port 8001
  or
  python main.py (runs on localhost:8001)
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
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

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

# Phase 4.1 safety infrastructure (optional, graceful degradation if unavailable)
try:
    from safety_infrastructure import (
        EpistemicValidator, QuestionAdjustedScorer, FactionGate, RegressionDetector
    )
    _PHASE4_SAFETY_AVAILABLE = True
except ImportError:
    _PHASE4_SAFETY_AVAILABLE = False

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


# --- Fact injection models (for internal agent use) ---

class Fact(BaseModel):
    """A single fact with confidence and source."""
    text: str = Field(..., description="The fact text")
    confidence: Optional[float] = Field(None, description="Confidence score (0-1)")
    source: Optional[str] = Field(None, description="Which engine returned this fact (GRAIN, CARTRIDGE, etc.)")


class FactsResponse(BaseModel):
    """Response for /api/facts endpoint - fact injection interface."""
    query: str = Field(..., description="The original query")
    facts: List[str] = Field(..., description="List of fact texts (when verbose=false)")
    facts_detailed: Optional[List[Fact]] = Field(None, description="List of facts with metadata (when verbose=true)")
    verbose: bool = Field(default=False, description="Whether confidence/source are included")
    limit: int = Field(default=3, description="Number of facts returned")


# --- OpenAI-compatible Chat Completions models (Phase 3D: SillyTavern integration) ---

class ChatMessage(BaseModel):
    """Message in OpenAI Chat Completions format."""
    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    """OpenAI Chat Completions request format."""
    model_config = ConfigDict(extra="ignore")  # Ignore extra fields (SillyTavern sends many)

    model: str = Field(default="kitbash", description="Model ID (ignored, always uses Kitbash)")
    messages: List[ChatMessage] = Field(..., description="List of messages")
    temperature: Optional[float] = Field(default=0.7, description="Temperature (ignored, Kitbash uses confidence)")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens (ignored)")
    top_p: Optional[float] = Field(default=1.0, description="Top-p (ignored)")
    top_k: Optional[int] = Field(default=None, description="Top-k (ignored)")
    frequency_penalty: Optional[float] = Field(default=0.0, description="Frequency penalty (ignored)")
    presence_penalty: Optional[float] = Field(default=0.0, description="Presence penalty (ignored)")
    stream: Optional[bool] = Field(default=False, description="Stream mode (not yet supported)")
    stop: Optional[List[str]] = Field(default=None, description="Stop sequences (ignored)")
    logit_bias: Optional[Dict[str, float]] = Field(default=None, description="Logit bias (ignored)")
    seed: Optional[int] = Field(default=None, description="Random seed (ignored)")


class ChatCompletionChoice(BaseModel):
    """Choice in Chat Completions response."""
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    """OpenAI Chat Completions response format."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str = "kitbash"
    choices: List[ChatCompletionChoice]
    usage: Dict[str, int]


class ModelInfo(BaseModel):
    """Model info in models list."""
    id: str
    object: str = "model"
    owned_by: str = "kitbash"
    permission: List[Dict[str, Any]] = Field(default_factory=list)


class ModelsResponse(BaseModel):
    """Response for /v1/models endpoint."""
    object: str = "list"
    data: List[ModelInfo]


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

        # Initialize Phase 4.1 background metabolism cycle and scheduler
        # Safety infrastructure provides optional validators; cycle degrades gracefully if absent
        if _PHASE4_SAFETY_AVAILABLE:
            bg_cycle = BackgroundMetabolismCycle(
                log_analyzer=None,  # Will be connected when Redis is available
                epistemic_validator=EpistemicValidator(),
                question_scorer=QuestionAdjustedScorer(),
                faction_gate=FactionGate(),
                regression_detector=RegressionDetector(),
            )
        else:
            bg_cycle = BackgroundMetabolismCycle()  # All deps None, graceful no-op
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

# --- CORS middleware for cross-origin requests (SillyTavern integration) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (can be restricted to specific hosts if needed)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/api/facts", response_model=FactsResponse)
async def api_facts(
    query: str,
    limit: int = 3,
    verbose: bool = False,
) -> FactsResponse:
    """
    Get grounded facts for a query (fact injection interface for internal agents).

    Returns top N facts with optional confidence scores and sources.

    Args:
        query: The question to get facts for
        limit: Maximum number of facts to return (default 3)
        verbose: Include confidence scores and sources (default false)

    Returns:
        FactsResponse with facts formatted for prompt injection
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if len(query) > 2000:
        raise HTTPException(status_code=400, detail="Query too long (max 2000 characters)")

    if limit < 1 or limit > 20:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 20")

    try:
        # Process query through orchestrator
        result: QueryResult = _orchestrator.process_query(query, {"source": "facts_injection"})

        logger.info(f"Facts request: query='{query[:50]}', limit={limit}, verbose={verbose}")

        # Extract facts from result
        # For now, we'll use the primary answer as a fact
        # In the future, we could extract multiple facts from layer_results
        facts_list = []

        if result.answer and result.answer != "I don't know.":
            facts_list.append({
                "text": result.answer,
                "confidence": result.confidence,
                "source": result.engine_name,
            })

        # Limit to requested number
        facts_list = facts_list[:limit]

        # Format response based on verbose flag
        if verbose:
            # Return detailed facts with confidence and source
            facts_detailed = [
                Fact(
                    text=f["text"],
                    confidence=round(f["confidence"], 2),
                    source=f["source"]
                )
                for f in facts_list
            ]
            return FactsResponse(
                query=query,
                facts=[],
                facts_detailed=facts_detailed,
                verbose=True,
                limit=len(facts_list),
            )
        else:
            # Return just the text (clean for prompt injection)
            facts_text = [f["text"] for f in facts_list]
            return FactsResponse(
                query=query,
                facts=facts_text,
                facts_detailed=None,
                verbose=False,
                limit=len(facts_list),
            )

    except Exception as e:
        logger.error(f"Facts request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Facts request failed: {str(e)}")


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


# --- Phase 3D: OpenAI-compatible Chat Completions endpoints (SillyTavern integration) ---

@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """
    OpenAI-compatible Chat Completions endpoint for SillyTavern integration.

    Converts OpenAI message format to Kitbash query format and routes through orchestrator.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty")

    try:
        logger.info(f"Chat completions request received with {len(request.messages)} messages")

        # Extract the user's latest message (last one from 'user' role)
        user_message = None
        for msg in reversed(request.messages):
            if msg.role == "user":
                user_message = msg.content
                break

        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found in request")

        logger.info(f"Extracted user message: {user_message[:100]}")

        # Process through Kitbash orchestrator
        result: QueryResult = _orchestrator.process_query(user_message, {"source": "openai_compat"})

        logger.info(f"Orchestrator returned: query_id={result.query_id}, answer={result.answer[:50] if result.answer else None}, confidence={result.confidence}")

        # Build OpenAI-compatible response
        import time as time_module
        response = ChatCompletionResponse(
            id=f"kitbash-{result.query_id}",
            created=int(time_module.time()),
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=result.answer or "No answer found"
                    ),
                    finish_reason="stop"
                )
            ],
            usage={
                "prompt_tokens": len(user_message.split()),
                "completion_tokens": len((result.answer or "").split()),
                "total_tokens": len(user_message.split()) + len((result.answer or "").split())
            }
        )

        logger.info(f"Returning OpenAI-compatible response")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completions request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat completions failed: {str(e)}")


@app.get("/v1/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """
    List available models (OpenAI-compatible endpoint).

    Returns Kitbash as the available model for SillyTavern model selection.
    """
    try:
        return ModelsResponse(
            data=[
                ModelInfo(id="kitbash"),
                ModelInfo(id="kitbash-grain"),
                ModelInfo(id="kitbash-cartridge"),
            ]
        )
    except Exception as e:
        logger.error(f"Models request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Models request failed: {str(e)}")


# --- Route aliases without /v1 prefix (for SillyTavern compatibility) ---

@app.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions_no_v1(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """Alias for /v1/chat/completions (SillyTavern compatibility)."""
    return await chat_completions(request)


@app.get("/models", response_model=ModelsResponse)
async def list_models_no_v1() -> ModelsResponse:
    """Alias for /v1/models (SillyTavern compatibility)."""
    return await list_models()


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Kitbash FastAPI server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
