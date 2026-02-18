"""
Kitbash CartridgeBuilder
Populates cartridges from various data formats

Supports:
- Markdown files (# heading = domain, ## heading = subdomain, list items = facts)
- CSV files (header row = metadata, one fact per row)
- JSON files (array of objects with content/metadata)
- Plain text files (one fact per line, optional metadata)
"""

import json
import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from kitbash_cartridge import (
    Cartridge, AnnotationMetadata, EpistemicLevel,
    Derivation
)


class CartridgeBuilder:
    """Build and populate cartridges from various data sources."""
    
    def __init__(self, cartridge_name: str, cartridge_path: str = "./cartridges"):
        """
        Initialize builder (doesn't create cartridge yet).
        
        Args:
            cartridge_name: Name for the cartridge
            cartridge_path: Parent directory for cartridge files
        """
        self.cartridge_name = cartridge_name
        self.cartridge_path = cartridge_path
        self.cart = Cartridge(cartridge_name, cartridge_path)
        self.fact_count = 0
    
    def build(self) -> Cartridge:
        """Create the cartridge and return it."""
        self.cart.create()
        print(f"✓ Created cartridge: {self.cartridge_name}")
        return self.cart
    
    def save(self) -> None:
        """Save cartridge to disk."""
        self.cart.save()
        print(f"✓ Saved {self.fact_count} facts to {self.cartridge_name}")
    
    def load_cartridge(self) -> Cartridge:
        """Load existing cartridge."""
        self.cart.load()
        return self.cart

    def _parse_yaml_frontmatter(self, text: str) -> Tuple[dict, str]:
        """
        Extract YAML frontmatter from markdown.
        
        Returns: (frontmatter_dict, remaining_markdown_text)
        """
        # Check if text starts with ---
        if not text.strip().startswith("---"):
            return {}, text  # No frontmatter
        
        # Find closing ---
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text  # Malformed, treat as no frontmatter
        
        yaml_text = parts[1]
        markdown_text = parts[2]
        
        # Parse YAML
        try:
            import yaml
            frontmatter = yaml.safe_load(yaml_text)
            return frontmatter or {}, markdown_text
        except ImportError:
            # Fallback: simple key-value parsing (no external dep)
            return self._parse_yaml_simple(yaml_text), markdown_text

    def _parse_yaml_simple(self, yaml_text: str) -> dict:
        """
        Simple YAML parser (no external dependencies).
        Only handles basic key: value and key: [item1, item2] formats.
        """
        result = {}
        for line in yaml_text.strip().split('\n'):
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Parse arrays [item1, item2]
            if value.startswith('[') and value.endswith(']'):
                items = value[1:-1].split(',')
                result[key] = [item.strip() for item in items]
            # Parse booleans
            elif value.lower() == 'true':
                result[key] = True
            elif value.lower() == 'false':
                result[key] = False
            # Parse numbers
            elif value.replace('.', '', 1).isdigit():
                result[key] = float(value) if '.' in value else int(value)
            # Parse strings
            else:
                result[key] = value.strip('"\'')  # Remove quotes if present
        
        return result

    def _apply_frontmatter(self, frontmatter: dict) -> None:
        """
        Apply YAML frontmatter to cartridge manifest and builder state.
        """
        from datetime import datetime
        
        if 'cartridge_name' in frontmatter:
            # Note: already set during __init__, but could override
            pass
        
        if not self.cart.manifest:
            self.cart.manifest = {}
        
        # Apply frontmatter fields to manifest
        self.cart.manifest['description'] = frontmatter.get('description', '')
        self.cart.manifest['epistemic_level'] = frontmatter.get('epistemic_level', 'L2_AXIOMATIC')
        self.cart.manifest['domain'] = frontmatter.get('domain', 'general')
        self.cart.manifest['tags'] = frontmatter.get('tags', [])
        self.cart.manifest['author'] = frontmatter.get('author', 'unknown')
        self.cart.manifest['created'] = frontmatter.get('created', datetime.now().isoformat())
        self.cart.manifest['baseline_confidence'] = frontmatter.get('baseline_confidence', 0.8)
        self.cart.manifest['temporal_scope'] = frontmatter.get('temporal_scope', None)

    def _parse_temporal_bounds(self, temporal_str: Optional[str]) -> dict:
        """
        Parse temporal bounds string into start/end ISO8601 dates.
        
        Returns: {
            'start': ISO8601 string or None,
            'end': ISO8601 string or None,
            'approximate': bool,
            'raw_format': str (for debugging)
        }
        """
        from datetime import datetime, timezone
        import re
        
        if not temporal_str:
            return {'start': None, 'end': None, 'approximate': False, 'raw_format': None}
        
        temporal_str = temporal_str.strip()
        
        # Handle "eternal" (no bounds)
        if temporal_str.lower() in ['eternal', 'always', 'indefinite']:
            return {'start': None, 'end': None, 'approximate': False, 'raw_format': temporal_str}
        
        # Handle "sometime" / "eventually" (unbounded future)
        if temporal_str.lower() in ['sometime', 'eventually']:
            return {'start': datetime.now(timezone.utc).isoformat(), 'end': None, 'approximate': True, 'raw_format': temporal_str}
        
        # Handle approximate future: "~5_billion_years"
        match = re.match(r'~(\d+)_(\w+)', temporal_str)
        if match:
            # Just use today as start, no end (approximate)
            return {'start': datetime.now(timezone.utc).isoformat(), 'end': None, 'approximate': True, 'raw_format': temporal_str}
        
        # Handle "X to Y" format
        if ' to ' in temporal_str:
            parts = temporal_str.split(' to ')
            start_str = parts[0].strip()
            end_str = parts[1].strip()
            
            start_date = self._parse_date_component(start_str)
            end_date = self._parse_date_component(end_str)
            
            return {'start': start_date, 'end': end_date, 'approximate': False, 'raw_format': temporal_str}
        
        # Single date (treat as start)
        single_date = self._parse_date_component(temporal_str)
        return {'start': single_date, 'end': None, 'approximate': False, 'raw_format': temporal_str}

    def _parse_date_component(self, date_str: str) -> Optional[str]:
        """
        Parse a single date component.
        
        Handles:
        - ISO8601: 2025-02-12
        - Year only: 2025
        - Keywords: past, future, today, now
        """
        from datetime import datetime, timezone
        
        date_str = date_str.strip().lower()
        
        # Keywords
        if date_str in ['past', 'beginning', 'always']:
            return None  # Unbounded past
        
        if date_str in ['future', 'forever']:
            return None  # Unbounded future
        
        if date_str in ['today', 'now']:
            return datetime.now(timezone.utc).isoformat()
        
        # Try ISO8601: 2025-02-12
        try:
            dt = datetime.fromisoformat(date_str + 'T00:00:00' if 'T' not in date_str else date_str)
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
        
        # Try year only: 2025
        if len(date_str) == 4 and date_str.isdigit():
            year = int(date_str)
            dt = datetime(year, 1, 1, tzinfo=timezone.utc)
            return dt.isoformat()
        
        # Try year-month: 2025-02
        if len(date_str) == 7 and '-' in date_str:
            try:
                dt = datetime.fromisoformat(date_str + '-01T00:00:00')
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass
        
        # Can't parse, return None
        print(f"⚠ Warning: Could not parse temporal bound: {date_str}")
        return None


    # ========================================================================
    # MARKDOWN FORMAT
    # ========================================================================
    
    def from_markdown(self, filepath: str, 
                 domain_pattern: str = "#",
                 subdomain_pattern: str = "##",
                 fact_pattern: str = "-") -> None:
        """
        Load facts from markdown file with optional YAML frontmatter.
        
        Format:
        ---
        cartridge_name: Physics
        epistemic_level: L0_EMPIRICAL
        domain: Physics
        baseline_confidence: 0.96
        ---
        
        # Domain
        ## Subdomain
        - Fact text | source | confidence | temporal_bounds
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # STEP 1: Parse YAML frontmatter
        frontmatter, markdown_content = self._parse_yaml_frontmatter(content)
        
        # STEP 2: Apply frontmatter to cartridge
        if frontmatter:
            self._apply_frontmatter(frontmatter)
        
        # STEP 3: Parse markdown facts
        lines = markdown_content.split('\n')
        current_domain = ""
        current_subdomains = []
        baseline_confidence = frontmatter.get('baseline_confidence', 0.8)
        
        for line in lines:
            line = line.rstrip()
            
            # Check for domain heading
            if line.startswith(domain_pattern + " "):
                current_domain = line.lstrip(domain_pattern).strip()
                current_subdomains = []
                if self.cart.manifest:
                    if current_domain not in self.cart.manifest.get("domains", []):
                        self.cart.manifest.setdefault("domains", []).append(current_domain)
                continue
            
            # Check for subdomain heading
            if line.startswith(subdomain_pattern + " "):
                subdomain = line.lstrip(subdomain_pattern).strip()
                if subdomain not in current_subdomains:
                    current_subdomains.append(subdomain)
                continue
            
            # Check for fact
            if line.startswith(fact_pattern + " "):
                fact_text = line.lstrip(fact_pattern).strip()
                
                # Parse: "content | source | confidence | temporal_bounds"
                parts = [p.strip() for p in fact_text.split("|")]
                fact_content = parts[0]
                source = parts[1] if len(parts) > 1 else "markdown"
                confidence = float(parts[2]) if len(parts) > 2 else baseline_confidence
                temporal_bounds = parts[3] if len(parts) > 3 else None
                
                # Parse temporal bounds
                temporal_validity = self._parse_temporal_bounds(temporal_bounds)
                
                # Get epistemic level from frontmatter or default
                epistemic_level_str = frontmatter.get('epistemic_level', 'L2_AXIOMATIC')
                try:
                    epistemic_level = EpistemicLevel[epistemic_level_str]
                except KeyError:
                    epistemic_level = EpistemicLevel.L2_AXIOMATIC
                
                # Create annotation
                ann = AnnotationMetadata(
                    fact_id=0,
                    confidence=confidence,
                    sources=[source],
                    context_domain=current_domain or frontmatter.get('domain', 'general'),
                    context_subdomains=current_subdomains,
                    epistemic_level=epistemic_level,
                    temporal_validity_start=temporal_validity['start'],
                    temporal_validity_end=temporal_validity['end'],
                )
                
                self.cart.add_fact(fact_content, ann)
                self.fact_count += 1
        
        print(f"✓ Loaded {self.fact_count} facts from {filepath}")


    
    # ========================================================================
    # CSV FORMAT
    # ========================================================================
    
    def from_csv(self, filepath: str, 
                domain_col: str = "domain",
                content_col: str = "content",
                confidence_col: Optional[str] = "confidence",
                source_col: Optional[str] = "source") -> None:
        """
        Load facts from CSV file.
        
        Expected columns:
        - content (required): fact text
        - domain (optional): domain name
        - confidence (optional): 0-1 value
        - source (optional): source reference
        - Any other columns treated as context tags
        
        Args:
            filepath: Path to CSV file
            domain_col: Column name for domain
            content_col: Column name for fact content
            confidence_col: Column name for confidence (optional)
            source_col: Column name for source (optional)
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                if not row.get(content_col):
                    continue
                
                content = row[content_col].strip()
                domain = row.get(domain_col, "").strip() or "general"
                confidence = float(row.get(confidence_col, "0.8")) if confidence_col else 0.8
                source = row.get(source_col, "csv").strip()
                
                # Collect other columns as context tags
                context_tags = [
                    v.strip() for k, v in row.items()
                    if k not in [content_col, domain_col, confidence_col, source_col]
                    and v and v.strip()
                ]
                
                ann = AnnotationMetadata(
                    fact_id=0,
                    confidence=confidence,
                    sources=[source],
                    context_domain=domain,
                    context_applies_to=context_tags,
                )
                
                self.cart.add_fact(content, ann)
                self.fact_count += 1
        
        print(f"✓ Loaded {self.fact_count} facts from {filepath}")
    
    # ========================================================================
    # JSON FORMAT
    # ========================================================================
    
    def from_json(self, filepath: str,
                 content_key: str = "content",
                 metadata_key: Optional[str] = "metadata") -> None:
        """
        Load facts from JSON file.
        
        Format:
        [
            {
                "content": "fact text",
                "metadata": {
                    "confidence": 0.9,
                    "domain": "name",
                    "sources": ["source1"]
                }
            }
        ]
        
        Args:
            filepath: Path to JSON file
            content_key: Key containing fact text
            metadata_key: Key containing metadata dict (optional)
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both list and single object
        if isinstance(data, dict):
            data = [data]
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            content = item.get(content_key)
            if not content:
                continue
            
            # Parse metadata if present
            meta = item.get(metadata_key, {}) if metadata_key else {}
            confidence = meta.get("confidence", 0.8)
            domain = meta.get("domain", "general")
            sources = meta.get("sources", [])
            applies_to = meta.get("applies_to", [])
            excludes = meta.get("excludes", [])
            
            ann = AnnotationMetadata(
                fact_id=0,
                confidence=confidence,
                sources=sources if sources else ["json"],
                context_domain=domain,
                context_applies_to=applies_to,
                context_excludes=excludes,
            )
            
            self.cart.add_fact(content, ann)
            self.fact_count += 1
        
        print(f"✓ Loaded {self.fact_count} facts from {filepath}")
    
    # ========================================================================
    # PLAIN TEXT FORMAT
    # ========================================================================
    
    def from_text(self, filepath: str,
                 domain: str = "general",
                 confidence: float = 0.7,
                 one_fact_per_line: bool = True) -> None:
        """
        Load facts from plain text file.
        
        Simple format: one fact per line, or multiline sentences.
        
        Args:
            filepath: Path to text file
            domain: Domain to assign all facts
            confidence: Default confidence for all facts
            one_fact_per_line: If False, split on sentence boundaries
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        if one_fact_per_line:
            lines = text.split('\n')
            facts = [line.strip() for line in lines if line.strip()]
        else:
            # Split on sentence boundaries
            facts = [s.strip() + "." for s in re.split(r'[.!?]+', text) if s.strip()]
        
        for fact in facts:
            if len(fact) > 10:  # Skip very short lines
                ann = AnnotationMetadata(
                    fact_id=0,
                    confidence=confidence,
                    sources=["text"],
                    context_domain=domain,
                )
                self.cart.add_fact(fact, ann)
                self.fact_count += 1
        
        print(f"✓ Loaded {self.fact_count} facts from {filepath}")
    
    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================
    
    def from_directory(self, dirpath: str,
                      pattern: str = "*",
                      auto_domain: bool = True) -> None:
        """
        Load facts from multiple files in a directory.
        Automatically detects format by extension.
        
        Args:
            dirpath: Directory path
            pattern: File pattern (default: all files)
            auto_domain: Use subdirectory names as domain (if True)
        """
        dirpath = Path(dirpath)
        if not dirpath.is_dir():
            raise NotADirectoryError(f"Not a directory: {dirpath}")
        
        files = list(dirpath.glob(pattern))
        for filepath in sorted(files):
            if filepath.is_file():
                domain = filepath.parent.name if auto_domain else None
                
                try:
                    if filepath.suffix == '.md':
                        self.from_markdown(str(filepath))
                    elif filepath.suffix == '.csv':
                        self.from_csv(str(filepath))
                    elif filepath.suffix == '.json':
                        self.from_json(str(filepath))
                    elif filepath.suffix == '.txt':
                        self.from_text(str(filepath), domain=domain or "general")
                except Exception as e:
                    print(f"⚠ Skipped {filepath}: {e}")
        
        print(f"✓ Processed {len(files)} files from {dirpath}")
    
    # ========================================================================
    # MANUAL OPERATIONS
    # ========================================================================
    
    def add_fact(self, content: str,
                domain: str = "general",
                confidence: float = 0.8,
                sources: Optional[List[str]] = None,
                context_tags: Optional[List[str]] = None) -> int:
        """
        Manually add a single fact.
        
        Args:
            content: Fact text
            domain: Domain/category
            confidence: 0-1 confidence score
            sources: List of sources
            context_tags: Tags describing where it applies
            
        Returns:
            fact_id
        """
        ann = AnnotationMetadata(
            fact_id=0,
            confidence=confidence,
            sources=sources or ["manual"],
            context_domain=domain,
            context_applies_to=context_tags or [],
        )
        
        fact_id = self.cart.add_fact(content, ann)
        self.fact_count += 1
        return fact_id
    
    def add_batch(self, facts: List[Tuple[str, str, float]],
                 domain: str = "general",
                 sources: Optional[List[str]] = None) -> List[int]:
        """
        Add multiple facts at once.
        
        Args:
            facts: List of (content, context_tag, confidence) tuples
            domain: Domain for all facts
            sources: Sources for all facts
            
        Returns:
            List of fact_ids
        """
        fact_ids = []
        for content, context_tag, confidence in facts:
            fact_id = self.add_fact(
                content,
                domain=domain,
                confidence=confidence,
                sources=sources,
                context_tags=[context_tag] if context_tag else None,
            )
            fact_ids.append(fact_id)
        return fact_ids
    
    # ========================================================================
    # MANIFEST UPDATES
    # ========================================================================
    
    def set_metadata(self, description: str = "",
                    domains: Optional[List[str]] = None,
                    tags: Optional[List[str]] = None,
                    author: str = "CartridgeBuilder") -> None:
        """
        Update cartridge manifest metadata.
        
        Args:
            description: Cartridge description
            domains: List of domains covered
            tags: List of tags
            author: Author name
        """
        if description:
            self.cart.manifest["description"] = description
        
        if domains:
            self.cart.manifest["domains"] = list(set(self.cart.manifest.get("domains", []) + domains))
        
        if tags:
            self.cart.manifest["tags"] = list(set(self.cart.manifest.get("tags", []) + tags))
        
        self.cart.manifest["author"] = author
    
    # ========================================================================
    # INTROSPECTION
    # ========================================================================
    
    def get_stats(self) -> Dict:
        """Get current builder stats."""
        return {
            "cartridge": self.cartridge_name,
            "facts_added": self.fact_count,
            "exists": self.cart.cartridge_dir.exists(),
        }


# ============================================================================
# EXAMPLE USAGE & PRESETS
# ============================================================================

def create_from_markdown_example():
    """Example: Create cartridge from markdown."""
    builder = CartridgeBuilder("example")
    builder.build()
    
    # Create a sample markdown file
    markdown = """
# Physics
## Thermodynamics
- Water boils at 100°C at sea level | Handbook_Physics | 0.99
- Temperature affects molecular motion | basic_science | 0.95
- Heat flows from hot to cold objects | Thermodynamics | 0.98

## Mechanics
- F = ma | Newton | 0.99
- Objects fall due to gravity | Observation | 0.95
"""
    
    with open("sample.md", "w") as f:
        f.write(markdown)
    
    builder.from_markdown("sample.md")
    builder.save()


def create_from_csv_example():
    """Example: Create cartridge from CSV."""
    import csv
    
    builder = CartridgeBuilder("example_csv")
    builder.build()
    
    # Create sample CSV
    with open("sample.csv", "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["content", "domain", "confidence", "source", "tags"])
        writer.writeheader()
        writer.writerow({
            "content": "PLA gels at 60°C",
            "domain": "bioplastics",
            "confidence": "0.92",
            "source": "Handbook_2023",
            "tags": "PLA,polymers"
        })
        writer.writerow({
            "content": "Synthetic polymers are stable",
            "domain": "materials",
            "confidence": "0.85",
            "source": "Research",
            "tags": "polymers,synthetic"
        })
    
    builder.from_csv("sample.csv", source_col="source")
    builder.save()


if __name__ == "__main__":
    print("Cartridge Builder Examples\n")
    
    # Example 1: Manual
    print("1. Manual fact addition:")
    builder = CartridgeBuilder("manual_example")
    builder.build()
    
    builder.add_fact("Water boils at 100°C", domain="physics", confidence=0.99)
    builder.add_fact("Gravity pulls downward", domain="physics", confidence=0.99)
    builder.add_fact("PLA requires 60°C for gelling", domain="bioplastics", confidence=0.92)
    
    builder.set_metadata(
        description="Basic physics and materials science",
        domains=["physics", "bioplastics"],
        tags=["temperature", "materials", "polymers"],
    )
    
    builder.save()
    print(f"Created: {builder.get_stats()}\n")
    
    # Example 2: From markdown
    print("2. From markdown:")
    markdown_content = """# Bioplastics
## PLA
- PLA requires 60°C ±5°C for optimal gelling | Handbook_2023 | 0.92
- Temperature affects polymer crystallinity | Research_2024 | 0.85

## General
- Synthetic polymers are more stable than natural ones | BasicScience | 0.9
"""
    
    # NEW:
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        temp_path = f.name
        f.write(markdown_content)
    
    try:
        builder2 = CartridgeBuilder("markdown_example")
        builder2.build()
        builder2.from_markdown(temp_path)
        builder2.save()
        print(f"Created: {builder2.get_stats()}\n")
    finally:
        Path(temp_path).unlink(missing_ok=True)
    
    print("✓ Examples complete")
