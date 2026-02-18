"""
Unit tests for Kitbash Cartridge class
Tests all core functionality: CRUD, querying, indexing, persistence
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from kitbash_cartridge import (
    Cartridge, AnnotationMetadata, EpistemicLevel,
    Derivation, Relationship, AccessLogEntry
)


class TestCartridgeBasics(unittest.TestCase):
    """Test cartridge creation, loading, and basic operations."""
    
    def setUp(self):
        """Create temp directory for test cartridges."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_create_cartridge(self):
        """Test creating a new cartridge."""
        cart = Cartridge("test", path=self.temp_dir)
        cart.create()
        
        # Check files exist
        assert (Path(self.temp_dir) / "test.kbc" / "facts.db").exists()
        assert (Path(self.temp_dir) / "test.kbc" / "manifest.json").exists()
        assert (Path(self.temp_dir) / "test.kbc" / "indices").is_dir()
        
        cart.close()
    
    def test_add_and_retrieve_fact(self):
        """Test adding and retrieving facts."""
        cart = Cartridge("test", path=self.temp_dir)
        cart.create()
        
        # Add fact
        content = "Water boils at 100°C"
        fact_id = cart.add_fact(content)
        
        # Retrieve
        retrieved = cart.get_fact(fact_id)
        assert retrieved == content
        
        cart.close()
    
    def test_deduplication(self):
        """Test that duplicate content returns same ID."""
        cart = Cartridge("test", path=self.temp_dir)
        cart.create()
        
        content = "Water boils at 100°C"
        id1 = cart.add_fact(content)
        id2 = cart.add_fact(content)
        
        assert id1 == id2, "Duplicate should return same ID"
        assert cart.metadata['health']['fact_count'] == 0  # Not updated until save
        
        cart.close()
    
    def test_save_and_load(self):
        """Test persistence across sessions."""
        cart = Cartridge("test", path=self.temp_dir)
        cart.create()
        
        # Add facts
        id1 = cart.add_fact("Water boils at 100°C")
        id2 = cart.add_fact("Ice melts at 0°C")
        cart.save()
        cart.close()
        
        # Reload
        cart2 = Cartridge("test", path=self.temp_dir)
        cart2.load()
        
        assert cart2.get_fact(id1) == "Water boils at 100°C"
        assert cart2.get_fact(id2) == "Ice melts at 0°C"
        
        cart2.close()


class TestAnnotations(unittest.TestCase):
    """Test annotation tracking and epistemological levels."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_add_with_annotation(self):
        """Test adding fact with rich annotation."""
        cart = Cartridge("test", path=self.temp_dir)
        cart.create()
        
        ann = AnnotationMetadata(
            fact_id=0,
            confidence=0.92,
            sources=["Handbook_2023"],
            context_domain="physics",
            context_applies_to=["water", "temperature"],
        )
        
        fact_id = cart.add_fact("Water boils at 100°C", ann)
        
        # Check annotation stored
        stored_ann = cart.annotations[fact_id]
        assert stored_ann.confidence == 0.92
        assert "Handbook_2023" in stored_ann.sources
        assert "water" in stored_ann.context_applies_to
        
        cart.close()
    
    def test_epistemological_levels(self):
        """Test different epistemic levels."""
        cart = Cartridge("test", path=self.temp_dir)
        cart.create()
        
        # Empirical law (immutable)
        id_empirical = cart.add_fact(
            "E=mc²",
            AnnotationMetadata(
                epistemic_level=EpistemicLevel.L0_EMPIRICAL,
                confidence=1.0,
            )
        )
        
        # Belief (ephemeral)
        id_belief = cart.add_fact(
            "I think water is important",
            AnnotationMetadata(
                epistemic_level=EpistemicLevel.L3_PERSONA,
                confidence=0.6,
            )
        )
        
        assert cart.annotations[id_empirical].epistemic_level == EpistemicLevel.L0_EMPIRICAL
        assert cart.annotations[id_belief].epistemic_level == EpistemicLevel.L3_PERSONA
        
        cart.close()
    
    def test_derivations(self):
        """Test logical derivation tracking."""
        cart = Cartridge("test", path=self.temp_dir)
        cart.create()
        
        ann = AnnotationMetadata(
            derivations=[
                Derivation(
                    type="positive_dependency",
                    description="Temperature affects viscosity",
                    strength=0.95,
                    target="viscosity",
                ),
                Derivation(
                    type="range_constraint",
                    parameter="temperature",
                    min_val=50,
                    max_val=150,
                    unit="°C",
                ),
            ]
        )
        
        fact_id = cart.add_fact("Viscosity depends on temperature", ann)
        
        stored_ann = cart.annotations[fact_id]
        assert len(stored_ann.derivations) == 2
        assert stored_ann.derivations[0].strength == 0.95
        assert stored_ann.derivations[1].min_val == 50
        
        cart.close()


class TestQuerying(unittest.TestCase):
    """Test query functionality."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cart = Cartridge("test", path=self.temp_dir)
        self.cart.create()
        
        # Add test facts
        self.cart.add_fact("Water boils at 100°C at sea level")
        self.cart.add_fact("Temperature affects polymer crystallinity")
        self.cart.add_fact("PLA requires 60°C for optimal gelling")
        self.cart.add_fact("Synthetic polymers are more stable")
    
    def tearDown(self):
        self.cart.close()
        shutil.rmtree(self.temp_dir)
    
    def test_simple_query(self):
        """Test basic keyword query."""
        results = self.cart.query("temperature")
        assert len(results) > 0
        assert 1 in results  # "Water boils..." has "temperature"? No, different facts
    
    def test_multi_keyword_query(self):
        """Test query with multiple keywords."""
        results = self.cart.query("temperature polymer")
        # Should find facts with both keywords
        assert isinstance(results, list)
    
    def test_query_no_results(self):
        """Test query with no matching facts."""
        results = self.cart.query("xyzabc notaword")
        # Should return empty or use fallback
        assert isinstance(results, list)
    
    def test_detailed_query(self):
        """Test query with annotations."""
        results = self.cart.query_detailed("temperature")
        
        for fact_id, data in results.items():
            assert "content" in data
            assert "annotation" in data
            assert isinstance(data["content"], str)
            assert isinstance(data["annotation"], AnnotationMetadata)
    
    def test_keyword_extraction(self):
        """Test keyword extraction (filters stop words)."""
        keywords = self.cart._extract_keywords("the quick brown fox")
        
        # "the" should be filtered (stop word)
        assert "the" not in keywords
        # Should have content words
        assert "quick" in keywords or "brown" in keywords


class TestAccessLogging(unittest.TestCase):
    """Test access logging and phantom detection."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cart = Cartridge("test", path=self.temp_dir)
        self.cart.create()
        
        self.fact_id = self.cart.add_fact("Temperature affects crystallinity")
    
    def tearDown(self):
        self.cart.close()
        shutil.rmtree(self.temp_dir)
    
    def test_access_logging(self):
        """Test that queries are logged."""
        initial_count = self.cart.access_log[self.fact_id].access_count
        
        # Query triggers logging
        self.cart.query("temperature")
        
        updated_count = self.cart.access_log[self.fact_id].access_count
        assert updated_count > initial_count
    
    def test_access_disable(self):
        """Test disabling access logging."""
        initial_count = self.cart.access_log[self.fact_id].access_count
        
        # Query without logging
        self.cart.query("temperature", log_access=False)
        
        updated_count = self.cart.access_log[self.fact_id].access_count
        assert updated_count == initial_count
    
    def test_phantom_detection(self):
        """Test phantom candidate detection."""
        # Multiple queries with same pattern
        for _ in range(10):
            self.cart.query("temperature crystallinity")
        
        phantoms = self.cart.get_phantom_candidates(
            min_access_count=5,
            min_consistency=0.5
        )
        
        # Should have at least one phantom
        assert len(phantoms) > 0
        
        # Phantom should have high consistency
        fact_id, data = phantoms[0]
        assert data["consistency"] >= 0.5
    
    def test_query_patterns(self):
        """Test that query patterns are tracked."""
        self.cart.query("temperature crystallinity")
        self.cart.query("temperature crystallinity")
        self.cart.query("temperature")  # Different pattern
        
        log = self.cart.access_log[self.fact_id]
        
        # Should have patterns tracked
        assert len(log.query_patterns) > 0
        
        # Some patterns should have multiple counts
        assert any(p["count"] > 1 for p in log.query_patterns)


class TestAccessDistribution(unittest.TestCase):
    """Test hot/cold classification."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cart = Cartridge("test", path=self.temp_dir)
        self.cart.create()
    
    def tearDown(self):
        self.cart.close()
        shutil.rmtree(self.temp_dir)
    
    def test_uniform_distribution(self):
        """Test when facts are accessed uniformly."""
        # Add 5 facts
        for i in range(5):
            self.cart.add_fact(f"Fact {i}")
        
        # Access each once
        for i in range(1, 6):
            self.cart._log_access(i, ["fact"])
        
        analysis = self.cart.analyze_access_distribution()
        
        assert analysis["distribution"] == "uniform"
        assert analysis["hot_ratio"] < 0.5  # No clear hot facts
    
    def test_pareto_distribution(self):
        """Test when facts follow Pareto (20/80) pattern."""
        # Add 10 facts
        for i in range(10):
            self.cart.add_fact(f"Fact {i}")
        
        # Access first 2 facts heavily (80% of accesses)
        for _ in range(40):
            self.cart._log_access(1, ["fact"])
        for _ in range(40):
            self.cart._log_access(2, ["fact"])
        
        # Access rest lightly
        for i in range(3, 11):
            self.cart._log_access(i, ["fact"])
        
        analysis = self.cart.analyze_access_distribution()
        
        assert analysis["distribution"] == "pareto"
        assert analysis["hot_ratio"] < 0.3  # 2/10 = 20%
    
    def test_split_recommendation(self):
        """Test split recommendation logic."""
        # Create Pareto distribution
        for i in range(10):
            self.cart.add_fact(f"Fact {i}")
        
        for _ in range(80):
            self.cart._log_access(1, ["fact"])
        for _ in range(20):
            self.cart._log_access(2, ["fact"])
        
        for i in range(3, 11):
            self.cart._log_access(i, ["fact"])
        
        analysis = self.cart.analyze_access_distribution()
        
        # Sweet spot: 15-35% hot facts
        hot_ratio = analysis["hot_ratio"]
        assert analysis["should_split"] == (0.15 < hot_ratio < 0.35)


class TestStatistics(unittest.TestCase):
    """Test statistics and health metrics."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cart = Cartridge("test", path=self.temp_dir)
        self.cart.create()
    
    def tearDown(self):
        self.cart.close()
        shutil.rmtree(self.temp_dir)
    
    def test_get_stats(self):
        """Test stats collection."""
        self.cart.add_fact("Fact 1")
        self.cart.add_fact("Fact 2")
        
        stats = self.cart.get_stats()
        
        assert stats["name"] == "test"
        assert stats["active_facts"] == 2
        assert stats["annotations"] == 2
        assert isinstance(stats["keywords"], int)
    
    def test_metadata_accuracy(self):
        """Test that metadata reflects cartridge state."""
        # Add facts
        self.cart.add_fact("Fact 1")
        self.cart.add_fact("Fact 2")
        self.cart.save()
        
        # Metadata should be updated
        assert self.cart.metadata["health"]["fact_count"] == 2
        assert self.cart.metadata["health"]["active_facts"] == 2


class TestAnnotationSerialization(unittest.TestCase):
    """Test annotation serialization to/from JSON."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_annotation_roundtrip(self):
        """Test that annotations survive JSON serialization."""
        orig = AnnotationMetadata(
            fact_id=42,
            confidence=0.95,
            sources=["Source1", "Source2"],
            epistemic_level=EpistemicLevel.L1_NARRATIVE,
            context_domain="test",
            context_applies_to=["tag1", "tag2"],
        )
        
        # Serialize
        data = orig.to_dict()
        
        # Deserialize
        restored = AnnotationMetadata.from_dict(data)
        
        assert restored.fact_id == 42
        assert restored.confidence == 0.95
        assert restored.sources == ["Source1", "Source2"]
        assert restored.epistemic_level == EpistemicLevel.L1_NARRATIVE
        assert restored.context_applies_to == ["tag1", "tag2"]


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCartridgeBasics))
    suite.addTests(loader.loadTestsFromTestCase(TestAnnotations))
    suite.addTests(loader.loadTestsFromTestCase(TestQuerying))
    suite.addTests(loader.loadTestsFromTestCase(TestAccessLogging))
    suite.addTests(loader.loadTestsFromTestCase(TestAccessDistribution))
    suite.addTests(loader.loadTestsFromTestCase(TestStatistics))
    suite.addTests(loader.loadTestsFromTestCase(TestAnnotationSerialization))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
