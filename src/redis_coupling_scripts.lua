-- src/redis_coupling_scripts.lua
-- Redis Lua Scripts for Epistemic Coupling Validation
-- 
-- Phase 3B.3: Coupling Geometry Implementation
-- Runs atomically inside Redis (no network roundtrips)
-- 
-- Each script measures disagreement (delta) between coupled layers
-- and assesses severity based on coupling constant (κ)
--
-- Performance target: <1ms per validation
-- Consistency: Atomic (all-or-nothing)

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Measure disagreement magnitude between two facts (0.0 to 1.0)
local function measure_delta(fact_a, fact_b, coupling_constant)
  -- fact_a and fact_b are JSON strings with:
  --   {confidence, content, epistemic_level}
  
  -- Deserialize (simplified - in production use cjson)
  -- For MVP: Just use string comparison
  
  if fact_a == fact_b then
    return 0.0  -- No disagreement
  end
  
  -- Placeholder: Simple heuristic for MVP
  -- Phase 4 can improve with semantic similarity
  local delta = 0.5  -- Medium disagreement by default
  
  return delta
end

-- Assess severity based on delta magnitude and coupling constant
local function assess_severity(delta, coupling_constant, layer_a, layer_b)
  -- κ (coupling_constant) determines threshold
  -- Default: κ = 1.0, threshold = 0.3
  
  local threshold = 0.3 / coupling_constant
  
  -- Severity hierarchy depends on which layers
  local severity = "LOW"
  
  if delta > threshold then
    if layer_a == "L0" or layer_a == "L1" or layer_b == "L0" or layer_b == "L1" then
      -- L0/L1 involved = higher severity
      if delta > threshold * 2 then
        severity = "CRITICAL"
      else
        severity = "HIGH"
      end
    else
      -- Higher layers = lower severity
      if delta > threshold * 1.5 then
        severity = "MEDIUM"
      else
        severity = "LOW"
      end
    end
  end
  
  return severity
end

-- ============================================================================
-- VALIDATION SCRIPTS (One per coupling rule)
-- ============================================================================

-- Script 1: Validate L0 (Observations) vs L1 (Axioms) Alignment
-- NEVER allow contradiction between ground truth and axioms
--
-- Redis key pattern:
--   query:{query_id}:spotlight:L0 → list of L0 facts
--   query:{query_id}:spotlight:L1 → list of L1 facts
--
local function validate_coupling_L0_L1()
  local query_id = KEYS[1]
  local coupling_constant = tonumber(ARGV[1]) or 1.0
  
  local l0_key = "query:" .. query_id .. ":spotlight:L0"
  local l1_key = "query:" .. query_id .. ":spotlight:L1"
  
  local l0_facts = redis.call("LRANGE", l0_key, 0, -1)
  local l1_facts = redis.call("LRANGE", l1_key, 0, -1)
  
  -- In MVP: Just check if lists exist and have content
  -- Phase 4 can do semantic checking
  
  local max_delta = 0.0
  local severity = "LOW"
  
  -- If both layers have facts, validate alignment
  if #l0_facts > 0 and #l1_facts > 0 then
    -- Placeholder: For MVP, always pass if facts exist
    -- (Real implementation would compare semantic content)
    max_delta = 0.0
    severity = "PASS"
  end
  
  -- Return: [status, delta_magnitude, severity]
  return {
    status = (severity == "PASS" or severity == "LOW") and "OK" or "FAIL",
    delta = max_delta,
    severity = severity,
    layer_a = "L0",
    layer_b = "L1"
  }
end

-- Script 2: Validate L1 (Axioms) vs L2 (Narrative) Alignment
-- L1 axioms must not be directly contradicted by L2 narrative
-- (L2 can be uncertain, but not contradictory)
--
local function validate_coupling_L1_L2()
  local query_id = KEYS[1]
  local coupling_constant = tonumber(ARGV[1]) or 1.0
  
  local l1_key = "query:" .. query_id .. ":spotlight:L1"
  local l2_key = "query:" .. query_id .. ":spotlight:L2"
  
  local l1_facts = redis.call("LRANGE", l1_key, 0, -1)
  local l2_facts = redis.call("LRANGE", l2_key, 0, -1)
  
  local max_delta = 0.0
  local severity = "LOW"
  
  -- If both layers populated, check for contradictions
  if #l1_facts > 0 and #l2_facts > 0 then
    -- Placeholder: In production, compare fact contents
    -- For MVP: Just verify both layers are populated without conflict
    max_delta = 0.0
    severity = "LOW"
  end
  
  -- Return: [status, delta_magnitude, severity]
  return {
    status = (severity == "LOW") and "OK" or "FLAG",
    delta = max_delta,
    severity = severity,
    layer_a = "L1",
    layer_b = "L2"
  }
end

-- Script 3: Validate L2 (Narrative) vs L4 (Intent) Rationalization
-- L2 narrative should rationalize L4 intent
-- (Why does character feel/intend something? The narrative should explain it)
--
local function validate_coupling_L2_L4()
  local query_id = KEYS[1]
  local coupling_constant = tonumber(ARGV[1]) or 1.0
  
  local l2_key = "query:" .. query_id .. ":spotlight:L2"
  local l4_key = "query:" .. query_id .. ":spotlight:L4"
  
  local l2_facts = redis.call("LRANGE", l2_key, 0, -1)
  local l4_facts = redis.call("LRANGE", l4_key, 0, -1)
  
  local max_delta = 0.0
  local severity = "LOW"
  
  if #l2_facts > 0 and #l4_facts > 0 then
    -- Both exist - check they cohere
    -- For MVP: Just log that both are present
    max_delta = 0.0
    severity = "LOW"
  elseif #l4_facts > 0 and #l2_facts == 0 then
    -- Intent exists but no narrative to justify it
    -- This is a MEDIUM severity mismatch
    max_delta = 0.5
    severity = "MEDIUM"
  else
    -- Narrative exists without associated intent, or neither exists
    max_delta = 0.0
    severity = "LOW"
  end
  
  return {
    status = (severity == "LOW") and "OK" or "FLAG",
    delta = max_delta,
    severity = severity,
    layer_a = "L2",
    layer_b = "L4"
  }
end

-- Script 4: Validate L4 (Intent) Gates L3/L5
-- L4 intent should gate L3 (heuristics) and L5 (persona)
-- L3 and L5 should be compatible with L4, or L4 explicitly overrides
--
local function validate_coupling_L4_gates()
  local query_id = KEYS[1]
  local coupling_constant = tonumber(ARGV[1]) or 1.0
  
  local l3_key = "query:" .. query_id .. ":spotlight:L3"
  local l4_key = "query:" .. query_id .. ":spotlight:L4"
  local l5_key = "query:" .. query_id .. ":spotlight:L5"
  
  local l3_facts = redis.call("LRANGE", l3_key, 0, -1)
  local l4_facts = redis.call("LRANGE", l4_key, 0, -1)
  local l5_facts = redis.call("LRANGE", l5_key, 0, -1)
  
  local max_delta = 0.0
  local severity = "LOW"
  
  -- If L4 (intent) exists, it gates L3 and L5
  if #l4_facts > 0 then
    -- Check if L3 or L5 contradict L4
    if #l3_facts > 0 or #l5_facts > 0 then
      -- For MVP: Just verify they all exist
      -- Phase 4 can check semantic compatibility
      max_delta = 0.0
      severity = "LOW"
    end
  end
  
  return {
    status = "OK",
    delta = max_delta,
    severity = severity,
    layer_a = "L4",
    layer_b = "L3_L5"
  }
end

-- ============================================================================
-- MASTER VALIDATION SCRIPT (Called from Python)
-- ============================================================================
-- 
-- This is the actual script registered with Redis
-- Input: query_id, layer_a, layer_b, coupling_constant
-- Output: JSON string with validation result
--
local function validate_coupling_master()
  local query_id = KEYS[1]
  local layer_a = ARGV[1]
  local layer_b = ARGV[2]
  local coupling_constant = tonumber(ARGV[3]) or 1.0
  
  local result = {}
  
  -- Route to appropriate validation function
  if layer_a == "L0" and layer_b == "L1" then
    result = validate_coupling_L0_L1()
  elseif layer_a == "L1" and layer_b == "L2" then
    result = validate_coupling_L1_L2()
  elseif layer_a == "L2" and layer_b == "L4" then
    result = validate_coupling_L2_L4()
  elseif layer_a == "L4" and (layer_b == "L3" or layer_b == "L5") then
    result = validate_coupling_L4_gates()
  else
    result = {
      status = "UNKNOWN",
      delta = 0.0,
      severity = "LOW",
      layer_a = layer_a,
      layer_b = layer_b
    }
  end
  
  -- Add metadata
  result.query_id = query_id
  result.coupling_constant = coupling_constant
  result.timestamp = redis.call("TIME")[1]
  
  -- Return as JSON-serializable table
  -- (Python will convert to JSON)
  return cjson.encode(result)
end

-- ============================================================================
-- HELPER SCRIPT: Record Coupling Delta
-- ============================================================================
-- Log a coupling validation result to the query's delta registry
--
local function record_coupling_delta()
  local query_id = KEYS[1]
  local delta_json = ARGV[1]  -- Already JSON from Python
  
  local deltas_key = "query:" .. query_id .. ":deltas"
  
  -- Append to list (one per validation)
  redis.call("LPUSH", deltas_key, delta_json)
  
  -- Keep TTL in sync with query expiration
  local ttl = redis.call("TTL", "query:" .. query_id .. ":metadata")
  if ttl > 0 then
    redis.call("EXPIRE", deltas_key, ttl)
  end
  
  return "OK"
end

-- ============================================================================
-- RETURN SCRIPTS AS TABLE
-- ============================================================================
-- These are called from Python via RedisSpotlight
-- Each script needs: name, keys, args, function
--
return {
  {
    name = "validate_coupling",
    keys = 1,  -- KEYS[1] = query_id
    args = 3,  -- ARGV[1] = layer_a, ARGV[2] = layer_b, ARGV[3] = coupling_constant
    func = validate_coupling_master
  },
  {
    name = "record_coupling_delta",
    keys = 1,  -- KEYS[1] = query_id
    args = 1,  -- ARGV[1] = delta_json
    func = record_coupling_delta
  }
}

-- ============================================================================
-- NOTES FOR IMPLEMENTATION
-- ============================================================================
--
-- 1. This uses Lua's cjson for JSON serialization
--    Ensure redis-py is configured with: decode_responses=True
--
-- 2. Each script runs atomically inside Redis
--    No transaction overhead, no network roundtrips
--    Guaranteed consistency
--
-- 3. Latency target: <1ms per validation
--    Current MVP version is O(list_length) due to LRANGE
--    Phase 4 can optimize with hash lookups
--
-- 4. For Phase 3B.3 MVP:
--    - These scripts do basic structural checks
--    - Semantic validation (detecting actual contradictions) comes Phase 4
--    - They always return a result (never fail/error)
--
-- 5. The result table is converted to JSON by Python
--    Then stored back in Redis as a delta event
--    Phase 4 metabolism reads these events for learning
--
