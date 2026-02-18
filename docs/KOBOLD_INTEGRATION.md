# Kobold.cpp Integration Guide

**Phase 3D: Using Kitbash as a grounded fact source for kobold.cpp**

This guide shows how to integrate Kitbash with kobold.cpp to augment LLM responses with factual information from crystallized knowledge bases.

---

## Overview

**The Problem:** LLMs hallucinate. They make up facts that sound plausible but are wrong.

**The Solution:** Before sending a prompt to kobold.cpp, query Kitbash for grounded facts and inject them into the context window.

**The Flow:**
1. User sends a query to your application
2. Your app calls Kitbash `/api/facts` endpoint
3. Kitbash returns top N facts (confidence + source)
4. Your app injects facts into the prompt sent to kobold.cpp
5. kobold.cpp generates a response grounded in real facts

---

## Prerequisites

### 1. Kitbash Running
```bash
cd /home/user/Kitbash_Project
python main.py
# Service starts on http://127.0.0.1:8001
```

### 2. Kobold.cpp Running
```bash
# In a separate terminal
./kobold.cpp  # or your launch command
# Typically on http://127.0.0.1:5001
```

### 3. Test Connectivity
```bash
# Check Kitbash
curl http://127.0.0.1:8001/health

# Check Kobold
curl http://127.0.0.1:5001/api/info
```

---

## Quick Start: Fact Injection Pattern

### The Endpoint

```
GET /api/facts?query=<question>&limit=<n>&verbose=<true|false>
```

### Basic Example (Python)

```python
import requests
import json

KITBASH_URL = "http://127.0.0.1:8001"
KOBOLD_URL = "http://127.0.0.1:5001"

def query_with_facts(user_question: str) -> str:
    """Query kobold.cpp with Kitbash facts in context."""

    # Step 1: Get facts from Kitbash (compact format)
    facts_response = requests.get(
        f"{KITBASH_URL}/api/facts",
        params={
            "query": user_question,
            "limit": 3,
            "verbose": False  # Just text, no metadata
        }
    )
    facts_data = facts_response.json()

    # Step 2: Build fact context
    if facts_data["facts"]:
        facts_text = "\n".join([f"• {f}" for f in facts_data["facts"]])
        fact_section = f"**Relevant Facts:**\n{facts_text}\n"
    else:
        fact_section = ""

    # Step 3: Build prompt with facts
    prompt = f"""{fact_section}

**Question:** {user_question}

**Answer:**"""

    # Step 4: Send to kobold.cpp
    response = requests.post(
        f"{KOBOLD_URL}/api/v1/generate",
        json={
            "prompt": prompt,
            "max_length": 200,
            "temperature": 0.7,
        }
    )

    result = response.json()
    return result["results"][0]["text"]

# Usage
answer = query_with_facts("What is photosynthesis?")
print(answer)
```

### Output

```
**Relevant Facts:**
• Photosynthesis is the process by which green plants and some other organisms use sunlight to synthesize nutrients from carbon dioxide and water
• Photosynthesis is essential for producing oxygen and fixing carbon in the biosphere

**Question:** What is photosynthesis?

**Answer:** Photosynthesis is a fundamental biological process that converts light energy into chemical energy stored in glucose. It occurs in plants, algae, and some bacteria...
```

---

## Modes: Verbose vs. Compact

### Compact Mode (Default)
**Use when:** You want clean text for injection into prompts

```bash
curl "http://127.0.0.1:8001/api/facts?query=what%20is%20DNA&verbose=false"
```

**Response:**
```json
{
  "query": "what is DNA",
  "facts": [
    "DNA (deoxyribonucleic acid) is a molecule that carries genetic instructions for life",
    "DNA stores information in a four-letter code: A, T, G, C"
  ],
  "verbose": false,
  "limit": 2
}
```

**Use in prompt:**
```
Relevant facts:
- DNA (deoxyribonucleic acid) is a molecule that carries genetic instructions for life
- DNA stores information in a four-letter code: A, T, G, C
```

### Verbose Mode
**Use when:** You want metadata (confidence, source) for debugging or quality filtering

```bash
curl "http://127.0.0.1:8001/api/facts?query=what%20is%20DNA&verbose=true"
```

**Response:**
```json
{
  "query": "what is DNA",
  "facts_detailed": [
    {
      "text": "DNA (deoxyribonucleic acid) is a molecule that carries genetic instructions for life",
      "confidence": 0.95,
      "source": "GRAIN"
    }
  ],
  "verbose": true,
  "limit": 1
}
```

**Use case:**
```python
# Only inject facts with high confidence
high_confidence_facts = [
    f["text"] for f in facts_detailed
    if f["confidence"] >= 0.9
]
```

---

## Controlling Fact Retrieval

### Limit Parameter (1–20, default 3)

```bash
# Get just 1 fact (most relevant)
curl "http://127.0.0.1:8001/api/facts?query=photosynthesis&limit=1"

# Get 5 facts (richer context)
curl "http://127.0.0.1:8001/api/facts?query=photosynthesis&limit=5"
```

**Guidance:**
- **limit=1:** For summarization (short answers)
- **limit=3:** For typical Q&A (balanced)
- **limit=5–10:** For detailed research (long-form)

### Query Phrasing

Kitbash works best with natural language questions:

✅ **Good:**
- "What is ATP?"
- "How does photosynthesis work?"
- "Explain mitochondria"

❌ **Poor:**
- "ATP" (too short, no context)
- "photosynthesis mechanism" (missing verb)
- "mitochondrion function" (singular/technical)

---

## Integration Patterns

### Pattern 1: Fact Injection Before Prompt

```python
def answer_question(question: str) -> str:
    # Get facts
    facts = get_facts(question, limit=3)

    # Build prompt with facts as context
    prompt = f"""Context facts:
{format_facts(facts)}

User question: {question}

Answer concisely:"""

    # Query LLM
    return query_llm(prompt)
```

### Pattern 2: Fact Grounding with Quality Filter

```python
def answer_question_grounded(question: str, min_confidence: float = 0.85) -> str:
    # Get facts with metadata
    facts = get_facts(question, verbose=True, limit=5)

    # Filter by confidence
    grounded = [f for f in facts if f["confidence"] >= min_confidence]

    if not grounded:
        # No high-confidence facts; fall back to LLM
        return query_llm(f"Answer: {question}")

    # Use grounded facts
    prompt = f"""These facts are highly reliable:
{format_facts_with_sources(grounded)}

User question: {question}

Your answer should incorporate the facts above:"""

    return query_llm(prompt)
```

### Pattern 3: Multi-Domain Context

```python
def answer_complex_question(question: str) -> str:
    # Get facts from multiple domains
    facts_1 = get_facts(f"{question}", limit=2)
    facts_2 = get_facts(f"background on {question}", limit=2)

    all_facts = facts_1["facts"] + facts_2["facts"]

    prompt = f"""Background facts:
{format_facts(all_facts)}

Question: {question}

Answer with reference to the facts:"""

    return query_llm(prompt)
```

---

## Performance Characteristics

### Latency Breakdown

| Operation | Latency | Notes |
|-----------|---------|-------|
| Kitbash `/api/facts` call | 1–200ms | Depends on engine (GRAIN <1ms, CARTRIDGE ~100ms) |
| Network overhead | <5ms | Local network |
| Fact formatting | <5ms | Python string ops |
| **Total overhead** | **<250ms** | Before LLM inference |
| kobold.cpp inference | 100ms–5s | Depends on model and token length |

**Bottom line:** Fact injection adds ~50–200ms total overhead, negligible compared to LLM inference.

### Token Count Impact

Facts are compact. Typical overhead:

| Scenario | Tokens | Impact |
|----------|--------|--------|
| 3 facts (compact) | 50–100 | ~3% of 4K context |
| 5 facts (compact) | 100–150 | ~4% of 4K context |
| 3 facts + sources | 80–120 | ~3% of 4K context |

**Recommendation:** Use `limit=3` by default; go to `limit=5` only if you have context budget.

---

## Error Handling

### API Errors

```python
import requests

def get_facts_safe(question: str, limit: int = 3) -> list:
    """Get facts with graceful fallback."""
    try:
        response = requests.get(
            "http://127.0.0.1:8001/api/facts",
            params={"query": question, "limit": limit, "verbose": False},
            timeout=5  # Don't hang forever
        )
        response.raise_for_status()
        return response.json()["facts"]
    except requests.exceptions.Timeout:
        print(f"Kitbash timeout for query: {question}")
        return []
    except requests.exceptions.ConnectionError:
        print("Kitbash unavailable; proceeding without facts")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []

# Usage: If facts fail, LLM still works
facts = get_facts_safe(question)
prompt = f"Facts: {facts}\n\nQuestion: {question}"
answer = query_llm(prompt)  # Works even if facts list is empty
```

### Empty Results

```python
def query_with_fallback(question: str) -> str:
    facts = get_facts(question, limit=3)

    if facts["facts"]:
        # Use facts
        context = "\n".join(facts["facts"])
        prompt = f"Facts:\n{context}\n\nQuestion: {question}"
    else:
        # No facts; query directly
        prompt = f"Question: {question}"

    return query_llm(prompt)
```

### Service Health Check

```python
def is_kitbash_healthy() -> bool:
    """Check if Kitbash is running."""
    try:
        response = requests.get("http://127.0.0.1:8001/health", timeout=2)
        return response.status_code == 200
    except:
        return False

# Before querying
if is_kitbash_healthy():
    answer = query_with_facts(question)
else:
    answer = query_llm(question)  # Fallback
```

---

## Example: Complete Integration Script

```python
#!/usr/bin/env python3
"""
Complete example: kobold.cpp + Kitbash integration
"""

import requests
import json
from typing import Optional, List

class KitbashKoboldClient:
    def __init__(
        self,
        kitbash_url: str = "http://127.0.0.1:8001",
        kobold_url: str = "http://127.0.0.1:5001"
    ):
        self.kitbash_url = kitbash_url
        self.kobold_url = kobold_url

    def get_facts(
        self,
        query: str,
        limit: int = 3,
        verbose: bool = False
    ) -> List[str]:
        """Fetch facts from Kitbash."""
        try:
            response = requests.get(
                f"{self.kitbash_url}/api/facts",
                params={"query": query, "limit": limit, "verbose": verbose},
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            return data.get("facts", []) or data.get("facts_detailed", [])
        except Exception as e:
            print(f"⚠️  Facts unavailable: {e}")
            return []

    def query_kobold(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        """Send prompt to kobold.cpp."""
        try:
            response = requests.post(
                f"{self.kobold_url}/api/v1/generate",
                json={
                    "prompt": prompt,
                    "max_length": max_tokens,
                    "temperature": 0.7,
                    "top_p": 0.9,
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()["results"][0]["text"]
        except Exception as e:
            print(f"❌ LLM error: {e}")
            return None

    def answer(self, question: str, use_facts: bool = True) -> str:
        """Answer a question, optionally with grounded facts."""

        # Get facts if requested
        facts_text = ""
        if use_facts:
            facts = self.get_facts(question, limit=3)
            if facts:
                facts_text = "**Known facts:**\n"
                for fact in facts:
                    text = fact if isinstance(fact, str) else fact["text"]
                    facts_text += f"• {text}\n"
                facts_text += "\n"

        # Build prompt
        prompt = f"""{facts_text}**Question:** {question}

**Answer:**"""

        # Get response
        answer = self.query_kobold(prompt)
        return answer or f"(Unable to generate answer)"

# Usage
if __name__ == "__main__":
    client = KitbashKoboldClient()

    questions = [
        "What is photosynthesis?",
        "How does DNA encode information?",
        "Explain the citric acid cycle",
    ]

    for q in questions:
        print(f"\n📝 {q}")
        print(f"✅ {client.answer(q)}\n")
        print("---")
```

---

## Debugging Tips

### Enable Verbose Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)

# Now you'll see all HTTP requests/responses
response = requests.get(f"{KITBASH_URL}/api/facts?query=DNA")
```

### Check Fact Quality

```bash
# See what facts are returned
curl -s "http://127.0.0.1:8001/api/facts?query=photosynthesis&verbose=true" | python3 -m json.tool

# If confidence is low (<0.7), the query may not match cartridge content
```

### Test Individual Engines

```bash
# See which engine returned facts
curl "http://127.0.0.1:8001/api/query?query=photosynthesis" | python3 -m json.tool
# Look at "engine_name": "GRAIN" or "CARTRIDGE"
```

### Monitor Latency

```python
import time

start = time.time()
facts = get_facts("question")
kitbash_time = time.time() - start

print(f"Kitbash latency: {kitbash_time * 1000:.1f}ms")

# If consistently >200ms, query may be hitting CARTRIDGE (slower)
# If <5ms, hitting GRAIN (very fast)
```

---

## When to Use / Not Use Kitbash

### ✅ Use Kitbash Injection When:
- User is asking factual questions (science, history, definitions)
- You want to reduce hallucinations
- Domain is in the cartridges (biochemistry, biology, physics, etc.)
- You have <200ms latency budget
- Context window isn't extremely tight

### ❌ Skip Kitbash When:
- Question is creative or opinion-based
- User is asking for code/tutorials
- Domain isn't in cartridges (facts will be empty)
- Latency is critical (<50ms required)
- You're already at token limit

---

## Next Steps

1. **Test locally** with the example script
2. **Measure latency** for your typical queries
3. **Evaluate fact quality** with verbose mode
4. **Tune limit parameter** based on your needs
5. **Add error handling** to your application

For cartridge content expansion (Phase 3E), see `docs/CARTRIDGE_EXPANSION.md` (coming soon).

---

## Support

If integration isn't working:

1. Check Kitbash is running: `curl http://127.0.0.1:8001/health`
2. Check Kobold is running: `curl http://127.0.0.1:5001/api/info`
3. Test fact retrieval directly: `curl "http://127.0.0.1:8001/api/facts?query=test"`
4. Check logs in both services for errors

---

**Phase 3D Complete** ✅
