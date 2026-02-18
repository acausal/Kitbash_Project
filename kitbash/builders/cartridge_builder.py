#!/usr/bin/env python3
"""
Cartridge Builder - Bootstrap Tool for Week 1
==============================================

Create properly-formatted cartridges from structured knowledge sources.

Usage:
    python cartridge_builder.py --input facts.md --name bioplastics --output ./cartridges/

Features:
    - Extract facts from markdown/text/CSV/JSON
    - Interactive annotation (confidence, sources, context)
    - Automatic indexing and hashing
    - Validation against cartridge spec
    - Preview before saving
"""

import json
import sqlite3
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import argparse


@dataclass
class Fact:
    """Single fact to be added to cartridge"""
    content: str
    content_hash: str
    created_at: str
    access_count: int = 0
    last_accessed: Optional[str] = None
    status: str = "active"


@dataclass
class Annotation:
    """Annotation for a fact"""
    fact_id: int
    metadata: Dict[str, Any]
    derivations: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    context: Dict[str, Any]
    nwp_encoding: Optional[str] = None


class CartridgeBuilder:
    """Build cartridges from structured knowledge sources"""
    
    def __init__(self, cartridge_name: str, output_dir: str = "./cartridges"):
        self.cartridge_name = cartridge_name
        self.output_dir = Path(output_dir)
        self.cart_path = self.output_dir / f"{cartridge_name}.kbc"
        
        # In-memory storage during building
        self.facts: List[Fact] = []
        self.annotations: List[Annotation] = []
        self.keyword_index: Dict[str, List[int]] = {}
        self.content_hash_index: Dict[str, int] = {}
        
        # Metadata
        self.metadata = {
            "cartridge_name": cartridge_name,
            "created_at": datetime.now().isoformat(),
            "version": "0.1.0",
            "status": "building"
        }
        
        print(f"Initialized CartridgeBuilder for '{cartridge_name}'")
    
    # ================================================================
    # FACT EXTRACTION FROM SOURCES
    # ================================================================
    
    def load_from_markdown(self, filepath: str, interactive: bool = True):
        """
        Extract facts from markdown file.
        
        Expects format:
        ## Section Name
        - Fact one
        - Fact two
        
        Or:
        1. Fact one
        2. Fact two
        """
        print(f"\n=== Loading from markdown: {filepath} ===\n")
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract bullet points and numbered lists
        facts_raw = []
        
        # Match bullet points: - Fact or * Fact
        bullet_pattern = r'^[\s]*[-*]\s+(.+)$'
        bullets = re.findall(bullet_pattern, content, re.MULTILINE)
        facts_raw.extend(bullets)
        
        # Match numbered lists: 1. Fact or 1) Fact
        numbered_pattern = r'^\s*\d+[.)]\s+(.+)$'
        numbered = re.findall(numbered_pattern, content, re.MULTILINE)
        facts_raw.extend(numbered)
        
        print(f"Found {len(facts_raw)} potential facts")
        
        if interactive:
            facts_raw = self._interactive_fact_selection(facts_raw)
        
        # Add facts with default annotations
        for fact_text in facts_raw:
            self.add_fact_with_annotation(
                fact_text,
                annotation_template="default"
            )
    
    def load_from_text(self, filepath: str, delimiter: str = "\n"):
        """
        Load from plain text file.
        Each line (or delimiter-separated chunk) is a fact.
        """
        print(f"\n=== Loading from text: {filepath} ===\n")
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        facts_raw = [f.strip() for f in content.split(delimiter) if f.strip()]
        
        print(f"Found {len(facts_raw)} facts")
        
        for fact_text in facts_raw:
            self.add_fact_with_annotation(
                fact_text,
                annotation_template="default"
            )
    
    def load_from_csv(self, filepath: str):
        """
        Load from CSV file.
        
        Expected columns:
        - fact: The fact text (required)
        - confidence: 0.0-1.0 (optional)
        - source: Source citation (optional)
        - domain: Domain tag (optional)
        - applies_to: Comma-separated contexts (optional)
        """
        import csv
        
        print(f"\n=== Loading from CSV: {filepath} ===\n")
        
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            facts_data = list(reader)
        
        print(f"Found {len(facts_data)} facts")
        
        for row in facts_data:
            fact_text = row['fact']
            
            # Build annotation from CSV columns
            annotation = self._build_annotation_from_csv(row)
            
            self.add_fact_with_annotation(
                fact_text,
                annotation_override=annotation
            )
    
    def load_from_json(self, filepath: str):
        """
        Load from JSON file.
        
        Expected format:
        [
            {
                "fact": "PLA requires 60°C for gelling",
                "confidence": 0.92,
                "sources": ["Handbook_2023"],
                "domain": "bioplastics",
                "applies_to": ["PLA", "synthetic_polymers"]
            },
            ...
        ]
        """
        print(f"\n=== Loading from JSON: {filepath} ===\n")
        
        with open(filepath, 'r') as f:
            facts_data = json.load(f)
        
        print(f"Found {len(facts_data)} facts")
        
        for item in facts_data:
            fact_text = item['fact']
            
            # Build annotation from JSON
            annotation = self._build_annotation_from_json(item)
            
            self.add_fact_with_annotation(
                fact_text,
                annotation_override=annotation
            )
    
    # ================================================================
    # FACT & ANNOTATION MANAGEMENT
    # ================================================================
    
    def add_fact_with_annotation(
        self, 
        fact_text: str, 
        annotation_template: str = "default",
        annotation_override: Optional[Dict] = None
    ):
        """
        Add a fact with its annotation.
        
        annotation_template options:
        - "default": Basic metadata only
        - "interactive": Prompt user for details
        - "minimal": Just the fact, no metadata
        """
        # Check for duplicate
        content_hash = self._compute_hash(fact_text)
        if content_hash in self.content_hash_index:
            print(f"⚠️  Skipping duplicate: {fact_text[:60]}...")
            return
        
        # Create fact
        fact = Fact(
            content=fact_text,
            content_hash=content_hash,
            created_at=datetime.now().isoformat()
        )
        
        fact_id = len(self.facts) + 1
        self.facts.append(fact)
        self.content_hash_index[content_hash] = fact_id
        
        # Create annotation
        if annotation_override:
            annotation_data = annotation_override
        elif annotation_template == "interactive":
            annotation_data = self._interactive_annotation(fact_text)
        elif annotation_template == "minimal":
            annotation_data = self._minimal_annotation()
        else:  # default
            annotation_data = self._default_annotation(fact_text)
        
        annotation = Annotation(
            fact_id=fact_id,
            **annotation_data
        )
        
        self.annotations.append(annotation)
        
        # Update keyword index
        self._index_fact(fact_id, fact_text, annotation_data)
        
        print(f"✓ Added fact #{fact_id}: {fact_text[:60]}...")
    
    def _default_annotation(self, fact_text: str) -> Dict:
        """Create default annotation"""
        keywords = self._extract_keywords(fact_text)
        
        return {
            "metadata": {
                "confidence": 0.75,  # Default medium confidence
                "sources": ["manual_entry"],
                "created_at": datetime.now().isoformat()
            },
            "derivations": [],
            "relationships": [],
            "context": {
                "domain": self.cartridge_name,
                "applies_to": keywords[:5]  # Top 5 keywords
            }
        }
    
    def _minimal_annotation(self) -> Dict:
        """Minimal annotation - just fact exists"""
        return {
            "metadata": {
                "confidence": 0.5,
                "sources": ["unverified"]
            },
            "derivations": [],
            "relationships": [],
            "context": {
                "domain": self.cartridge_name
            }
        }
    
    def _interactive_annotation(self, fact_text: str) -> Dict:
        """Prompt user for annotation details"""
        print(f"\n--- Annotating: {fact_text[:60]}... ---")
        
        confidence = float(input("Confidence (0.0-1.0) [0.75]: ") or "0.75")
        sources = input("Sources (comma-separated) [manual]: ") or "manual"
        sources_list = [s.strip() for s in sources.split(",")]
        
        domain = input(f"Domain [{self.cartridge_name}]: ") or self.cartridge_name
        applies_to = input("Applies to (comma-separated): ")
        applies_to_list = [a.strip() for a in applies_to.split(",")] if applies_to else []
        
        return {
            "metadata": {
                "confidence": confidence,
                "sources": sources_list,
                "created_at": datetime.now().isoformat()
            },
            "derivations": [],
            "relationships": [],
            "context": {
                "domain": domain,
                "applies_to": applies_to_list
            }
        }
    
    def _build_annotation_from_csv(self, row: Dict) -> Dict:
        """Build annotation from CSV row"""
        confidence = float(row.get('confidence', 0.75))
        source = row.get('source', 'csv_import')
        domain = row.get('domain', self.cartridge_name)
        applies_to = row.get('applies_to', '').split(',') if row.get('applies_to') else []
        applies_to = [a.strip() for a in applies_to if a.strip()]
        
        return {
            "metadata": {
                "confidence": confidence,
                "sources": [source],
                "created_at": datetime.now().isoformat()
            },
            "derivations": [],
            "relationships": [],
            "context": {
                "domain": domain,
                "applies_to": applies_to
            }
        }
    
    def _build_annotation_from_json(self, item: Dict) -> Dict:
        """Build annotation from JSON item"""
        return {
            "metadata": {
                "confidence": item.get('confidence', 0.75),
                "sources": item.get('sources', ['json_import']),
                "created_at": datetime.now().isoformat()
            },
            "derivations": item.get('derivations', []),
            "relationships": item.get('relationships', []),
            "context": {
                "domain": item.get('domain', self.cartridge_name),
                "applies_to": item.get('applies_to', [])
            }
        }
    
    # ================================================================
    # INDEXING
    # ================================================================
    
    def _index_fact(self, fact_id: int, fact_text: str, annotation: Dict):
        """Add fact to keyword index"""
        keywords = self._extract_keywords(fact_text)
        
        # Add keywords from context
        if 'context' in annotation and 'applies_to' in annotation['context']:
            keywords.extend(annotation['context']['applies_to'])
        
        # Add to index
        for keyword in set(keywords):  # Deduplicate
            kw_lower = keyword.lower()
            if kw_lower not in self.keyword_index:
                self.keyword_index[kw_lower] = []
            self.keyword_index[kw_lower].append(fact_id)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text (simplified)"""
        # Remove punctuation and split
        text_clean = re.sub(r'[^\w\s°±-]', ' ', text)
        words = text_clean.split()
        
        # Filter stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
            'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
            'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can'
        }
        
        keywords = [
            w for w in words 
            if len(w) > 2 and w.lower() not in stopwords
        ]
        
        return keywords
    
    # ================================================================
    # UTILITIES
    # ================================================================
    
    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content"""
        return "sha256:" + hashlib.sha256(content.encode()).hexdigest()
    
    def _interactive_fact_selection(self, facts_raw: List[str]) -> List[str]:
        """Let user select which facts to include"""
        print("\n--- Fact Selection ---")
        print("Review each fact. Press Enter to include, 's' to skip, 'q' to quit:\n")
        
        selected = []
        for i, fact in enumerate(facts_raw, 1):
            response = input(f"[{i}/{len(facts_raw)}] {fact[:70]}... [Enter/s/q]: ").strip().lower()
            
            if response == 'q':
                print("Stopping selection.")
                break
            elif response == 's':
                print("  ⊗ Skipped")
                continue
            else:
                selected.append(fact)
                print("  ✓ Added")
        
        print(f"\nSelected {len(selected)}/{len(facts_raw)} facts")
        return selected
    
    # ================================================================
    # PREVIEW & VALIDATION
    # ================================================================
    
    def preview(self):
        """Preview cartridge before saving"""
        print(f"\n{'='*60}")
        print(f"CARTRIDGE PREVIEW: {self.cartridge_name}")
        print(f"{'='*60}\n")
        
        print(f"Facts: {len(self.facts)}")
        print(f"Annotations: {len(self.annotations)}")
        print(f"Keyword index size: {len(self.keyword_index)} keywords")
        print(f"Content hash index: {len(self.content_hash_index)} unique hashes")
        
        # Show sample facts
        print(f"\n--- Sample Facts (first 5) ---")
        for i, fact in enumerate(self.facts[:5], 1):
            ann = self.annotations[i-1]
            conf = ann.metadata.get('confidence', 'N/A')
            print(f"{i}. [{conf:.2f}] {fact.content[:70]}...")
        
        # Show keyword distribution
        print(f"\n--- Top Keywords ---")
        sorted_kw = sorted(self.keyword_index.items(), key=lambda x: len(x[1]), reverse=True)
        for kw, fact_ids in sorted_kw[:10]:
            print(f"  {kw}: {len(fact_ids)} facts")
        
        # Validation
        print(f"\n--- Validation ---")
        issues = self._validate()
        if issues:
            print("⚠️  Issues found:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✓ All checks passed")
        
        print(f"\n{'='*60}\n")
    
    def _validate(self) -> List[str]:
        """Validate cartridge structure"""
        issues = []
        
        # Check fact count
        if len(self.facts) == 0:
            issues.append("No facts added")
        
        # Check annotation count matches
        if len(self.facts) != len(self.annotations):
            issues.append(f"Fact/annotation mismatch: {len(self.facts)} facts, {len(self.annotations)} annotations")
        
        # Check for low confidence facts
        low_conf = [a for a in self.annotations if a.metadata.get('confidence', 1.0) < 0.5]
        if low_conf:
            issues.append(f"{len(low_conf)} facts have confidence < 0.5")
        
        # Check for missing sources
        no_source = [a for a in self.annotations if not a.metadata.get('sources')]
        if no_source:
            issues.append(f"{len(no_source)} facts missing sources")
        
        return issues
    
    # ================================================================
    # SAVE TO DISK
    # ================================================================
    
    def save(self, force: bool = False):
        """Save cartridge to disk"""
        if self.cart_path.exists() and not force:
            response = input(f"⚠️  Cartridge '{self.cartridge_name}' already exists. Overwrite? [y/N]: ")
            if response.lower() != 'y':
                print("Save cancelled.")
                return
        
        print(f"\n=== Saving cartridge to {self.cart_path} ===\n")
        
        # Create directory structure
        self.cart_path.mkdir(parents=True, exist_ok=True)
        indices_path = self.cart_path / "indices"
        indices_path.mkdir(exist_ok=True)
        
        # Save facts.db
        self._save_facts_db()
        
        # Save annotations.jsonl
        self._save_annotations()
        
        # Save indices
        self._save_indices()
        
        # Save metadata
        self._save_metadata()
        
        # Save manifest
        self._save_manifest()
        
        print(f"\n✓ Cartridge saved successfully!")
        print(f"  Location: {self.cart_path}")
        print(f"  Facts: {len(self.facts)}")
        print(f"  Size: {self._calculate_size()} KB")
    
    def _save_facts_db(self):
        """Save facts to SQLite database"""
        db_path = self.cart_path / "facts.db"
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)
        
        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON facts(content_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_count ON facts(access_count DESC)")
        
        # Insert facts
        for i, fact in enumerate(self.facts, 1):
            cursor.execute("""
                INSERT INTO facts (id, content_hash, content, created_at, access_count, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (i, fact.content_hash, fact.content, fact.created_at, fact.access_count, fact.status))
        
        conn.commit()
        conn.close()
        
        print(f"✓ Saved facts.db ({len(self.facts)} facts)")
    
    def _save_annotations(self):
        """Save annotations to JSONL"""
        jsonl_path = self.cart_path / "annotations.jsonl"
        
        with open(jsonl_path, 'w') as f:
            for ann in self.annotations:
                ann_dict = {
                    "fact_id": ann.fact_id,
                    "metadata": ann.metadata,
                    "derivations": ann.derivations,
                    "relationships": ann.relationships,
                    "context": ann.context
                }
                if ann.nwp_encoding:
                    ann_dict["nwp_encoding"] = ann.nwp_encoding
                
                f.write(json.dumps(ann_dict) + "\n")
        
        print(f"✓ Saved annotations.jsonl ({len(self.annotations)} annotations)")
    
    def _save_indices(self):
        """Save index files"""
        indices_path = self.cart_path / "indices"
        
        # Keyword index
        keyword_path = indices_path / "keyword.idx"
        with open(keyword_path, 'w') as f:
            json.dump(self.keyword_index, f, indent=2)
        print(f"✓ Saved keyword.idx ({len(self.keyword_index)} keywords)")
        
        # Content hash index
        hash_path = indices_path / "content_hash.idx"
        with open(hash_path, 'w') as f:
            json.dump(self.content_hash_index, f, indent=2)
        print(f"✓ Saved content_hash.idx ({len(self.content_hash_index)} hashes)")
        
        # Access log (empty for new cartridge)
        access_path = indices_path / "access_log.idx"
        with open(access_path, 'w') as f:
            json.dump({}, f, indent=2)
        print(f"✓ Saved access_log.idx (empty)")
    
    def _save_metadata(self):
        """Save metadata.json"""
        metadata = {
            "cartridge_name": self.cartridge_name,
            "created_at": self.metadata["created_at"],
            "last_updated": datetime.now().isoformat(),
            "version": self.metadata["version"],
            "status": "active",
            "split_status": "intact",
            "health": {
                "fact_count": len(self.facts),
                "active_facts": len([f for f in self.facts if f.status == "active"]),
                "annotation_count": len(self.annotations),
                "grain_count": 0,
                "avg_confidence": sum(a.metadata.get('confidence', 0) for a in self.annotations) / len(self.annotations) if self.annotations else 0
            }
        }
        
        metadata_path = self.cart_path / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✓ Saved metadata.json")
    
    def _save_manifest(self):
        """Save manifest.json"""
        # Extract domains from annotations
        domains = set()
        tags = set()
        for ann in self.annotations:
            if 'domain' in ann.context:
                domains.add(ann.context['domain'])
            if 'applies_to' in ann.context:
                tags.update(ann.context['applies_to'])
        
        manifest = {
            "cartridge_name": self.cartridge_name,
            "version": self.metadata["version"],
            "api_version": "1.0",
            "created": self.metadata["created_at"],
            "last_updated": datetime.now().isoformat(),
            "author": "CartridgeBuilder",
            "description": f"Knowledge cartridge for {self.cartridge_name}",
            "domains": list(domains),
            "tags": list(tags)[:20],  # Limit to top 20
            "dependencies": [],
            "fact_count": len(self.facts)
        }
        
        manifest_path = self.cart_path / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"✓ Saved manifest.json")
    
    def _calculate_size(self) -> int:
        """Calculate total cartridge size in KB"""
        total_bytes = 0
        for file in self.cart_path.rglob("*"):
            if file.is_file():
                total_bytes += file.stat().st_size
        return total_bytes // 1024


# ================================================================
# CLI INTERFACE
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Build Kitbash cartridges from structured knowledge"
    )
    parser.add_argument("--name", required=True, help="Cartridge name")
    parser.add_argument("--input", help="Input file (markdown, text, CSV, JSON)")
    parser.add_argument("--format", choices=["markdown", "text", "csv", "json"], help="Input format (auto-detected if not specified)")
    parser.add_argument("--output", default="./cartridges", help="Output directory")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode (select facts, annotate)")
    parser.add_argument("--preview", action="store_true", help="Preview before saving")
    parser.add_argument("--force", action="store_true", help="Overwrite existing cartridge")
    
    args = parser.parse_args()
    
    # Initialize builder
    builder = CartridgeBuilder(args.name, args.output)
    
    # Load input if provided
    if args.input:
        input_path = Path(args.input)
        
        # Auto-detect format
        if not args.format:
            suffix = input_path.suffix.lower()
            format_map = {
                '.md': 'markdown',
                '.txt': 'text',
                '.csv': 'csv',
                '.json': 'json'
            }
            args.format = format_map.get(suffix, 'text')
        
        # Load based on format
        if args.format == "markdown":
            builder.load_from_markdown(str(input_path), interactive=args.interactive)
        elif args.format == "text":
            builder.load_from_text(str(input_path))
        elif args.format == "csv":
            builder.load_from_csv(str(input_path))
        elif args.format == "json":
            builder.load_from_json(str(input_path))
    
    # Preview if requested
    if args.preview or not args.input:
        builder.preview()
        
        if not args.input:
            print("\nNo input file provided. Exiting.")
            return
    
    # Save
    save_response = input("\nSave cartridge? [Y/n]: ").strip().lower()
    if save_response in ['', 'y', 'yes']:
        builder.save(force=args.force)
    else:
        print("Save cancelled.")


if __name__ == "__main__":
    main()
