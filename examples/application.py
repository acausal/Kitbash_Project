#!/usr/bin/env python3
"""
Complete example: Fact injection into kobold.cpp
Run this script and ask questions!
"""

import requests
import sys
from typing import List, Optional

KITBASH_URL = "http://127.0.0.1:8001"
KOBOLD_URL = "http://127.0.0.1:5001"

class KitbashKoboldApp:
    """Simple REPL for fact-injected question answering."""

    def __init__(self):
        self.facts_cache = {}

    def is_service_available(self, url: str, name: str) -> bool:
        """Check if a service is running."""
        try:
            requests.get(url + "/health" if "kitbash" in url.lower() else url + "/api/info", timeout=2)
            print(f"  ✅ {name} available")
            return True
        except:
            print(f"  ❌ {name} not available at {url}")
            return False

    def startup_check(self) -> bool:
        """Verify services are running."""
        print("Starting up...")
        if not self.is_service_available(KITBASH_URL, "Kitbash"):
            return False
        if not self.is_service_available(KOBOLD_URL, "Kobold.cpp"):
            return False
        print("✅ Ready!\n")
        return True

    def get_facts(self, query: str, limit: int = 3) -> List[str]:
        """Retrieve facts from Kitbash."""
        try:
            response = requests.get(
                f"{KITBASH_URL}/api/facts",
                params={"query": query, "limit": limit, "verbose": False},
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            return data.get("facts", [])
        except Exception as e:
            print(f"⚠️  Could not fetch facts: {e}")
            return []

    def query_llm(self, prompt: str, max_tokens: int = 250) -> Optional[str]:
        """Send prompt to kobold.cpp and get response."""
        try:
            response = requests.post(
                f"{KOBOLD_URL}/api/v1/generate",
                json={
                    "prompt": prompt,
                    "max_length": max_tokens,
                    "temperature": 0.7,
                    "top_p": 0.9,
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result["results"][0]["text"]
        except requests.exceptions.Timeout:
            print("⏱️  LLM timeout (model generating...)")
            return None
        except Exception as e:
            print(f"❌ LLM error: {e}")
            return None

    def answer(self, question: str, use_facts: bool = True) -> str:
        """Answer a question with optional fact injection."""

        # Get facts
        facts = []
        if use_facts:
            facts = self.get_facts(question, limit=3)

        # Build prompt
        if facts:
            facts_section = "**Grounded Facts:**\n"
            for i, fact in enumerate(facts, 1):
                facts_section += f"{i}. {fact}\n"
            prompt = f"""{facts_section}
**Question:** {question}

**Answer:**"""
        else:
            prompt = f"Question: {question}\n\nAnswer:"

        # Query LLM
        answer = self.query_llm(prompt)
        if answer:
            return answer.strip()
        else:
            return "(Unable to generate answer)"

    def run_interactive(self) -> None:
        """Run interactive REPL."""
        print("💡 Fact-Injected Q&A with Kobold.cpp")
        print("=" * 50)
        print("Type questions and get grounded answers!")
        print("Commands: /facts (show last facts), /quit (exit)\n")

        last_facts = []

        while True:
            try:
                question = input("❓ You: ").strip()

                if not question:
                    continue

                if question.lower() == "/quit":
                    print("👋 Goodbye!")
                    break

                if question.lower() == "/facts":
                    if last_facts:
                        print("\n📚 Last facts used:")
                        for fact in last_facts:
                            print(f"  • {fact}")
                        print()
                    else:
                        print("(No facts retrieved yet)\n")
                    continue

                print("\n🤔 Thinking...")

                # Get facts
                facts = self.get_facts(question, limit=3)
                last_facts = facts

                if facts:
                    print("\n📚 Using facts:")
                    for i, fact in enumerate(facts, 1):
                        print(f"  {i}. {fact[:80]}...")

                # Build and query
                if facts:
                    facts_section = "**Grounded Facts:**\n"
                    for i, fact in enumerate(facts, 1):
                        facts_section += f"{i}. {fact}\n"
                    prompt = f"""{facts_section}
**Question:** {question}

**Answer:**"""
                else:
                    print("\n⚠️  No facts found for this query")
                    prompt = f"Question: {question}\n\nAnswer:"

                # Query LLM
                print("\n💭 Generating answer...")
                answer = self.query_llm(prompt)

                if answer:
                    print(f"\n🤖 Assistant: {answer.strip()}\n")
                else:
                    print("\n(Failed to generate answer)\n")

            except KeyboardInterrupt:
                print("\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")

    def run_demo(self) -> None:
        """Run demo with preset questions."""
        demo_questions = [
            "What is ATP?",
            "How does photosynthesis work?",
            "Explain mitochondria",
        ]

        print("\n📋 DEMO MODE")
        print("=" * 50)

        for question in demo_questions:
            print(f"\n❓ {question}")
            answer = self.answer(question, use_facts=True)
            print(f"✅ {answer}\n")

if __name__ == "__main__":
    app = KitbashKoboldApp()

    if not app.startup_check():
        print("\n❌ Cannot start: Services not available")
        print("\nMake sure to run:")
        print("  1. Kitbash: python /home/user/Kitbash_Project/main.py")
        print("  2. Kobold.cpp: ./kobold.cpp (or your launch command)")
        sys.exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        app.run_demo()
    else:
        app.run_interactive()
