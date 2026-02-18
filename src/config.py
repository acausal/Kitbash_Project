"""
Configuration loader for Kitbash Phase 3B infrastructure.

Loads configuration from:
1. Environment variables (highest priority)
2. .env file (via python-dotenv)
3. YAML config file (fallback)
4. Hardcoded defaults (lowest priority)

This design ensures Docker compatibility (env vars) while supporting
local development convenience (YAML fallback).
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field, field_validator, ConfigDict


logger = logging.getLogger(__name__)


class RedisConfig(BaseModel):
    """Redis connection configuration."""
    model_config = ConfigDict(validate_assignment=True)

    host: str = Field(default="localhost", description="Redis server host")
    port: int = Field(default=6379, description="Redis server port")
    db: int = Field(default=0, description="Redis database number")
    password: Optional[str] = Field(default=None, description="Redis password")
    connection_timeout: int = Field(default=5, description="Connection timeout in seconds")
    socket_timeout: int = Field(default=5, description="Socket timeout in seconds")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")


class LayerConfig(BaseModel):
    """Configuration for a single inference layer."""
    name: str
    timeout_ms: int
    enabled: bool
    description: str


class WorkerConfig(BaseModel):
    """Configuration for a subprocess worker."""
    host: str
    port: int
    enabled: bool
    retry_attempts: int = 3
    retry_backoff_ms: int = 100


class DiagnosticsConfig(BaseModel):
    """Diagnostics and monitoring configuration."""
    redis_enabled: bool = True
    log_retention_days: int = 7
    metric_collection: bool = True
    health_check_interval_ms: int = 5000
    event_buffer_size: int = 1000


class PerformanceConfig(BaseModel):
    """Performance tuning configuration."""
    grain_cache_size: int = 1000
    cartridge_cache_size: int = 100
    consensus_confidence_threshold: float = 0.85
    escalation_confidence_threshold: float = 0.60
    query_parallelization: bool = False

    @field_validator('consensus_confidence_threshold', 'escalation_confidence_threshold')
    @classmethod
    def validate_thresholds(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        return v


class KitbashConfig(BaseModel):
    """Main Kitbash configuration model."""
    model_config = ConfigDict(validate_assignment=True)

    redis: RedisConfig
    kitbash: Dict[str, Any]
    layers: Dict[str, LayerConfig]
    workers: Dict[str, WorkerConfig]
    diagnostics: DiagnosticsConfig
    performance: PerformanceConfig
    redis_keys: Dict[str, str]


class ConfigLoader:
    """
    Loads and manages Kitbash configuration.

    Priority order:
    1. Environment variables (REDIS_HOST, REDIS_PORT, etc.)
    2. .env file (via python-dotenv)
    3. YAML config file (kitbash_config.yaml)
    4. Hardcoded defaults
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config loader.

        Args:
            config_path: Path to YAML config file. Defaults to ./kitbash_config.yaml
        """
        self.config_path = config_path or os.getenv(
            "KITBASH_CONFIG_PATH",
            "./kitbash_config.yaml"
        )
        self.config: Optional[KitbashConfig] = None
        self._load()

    def _load(self) -> None:
        """Load configuration from all sources."""
        # Load YAML as base
        yaml_config = self._load_yaml()

        # Override with environment variables
        env_config = self._load_env_overrides(yaml_config)

        # Validate with Pydantic
        try:
            self.config = KitbashConfig(**env_config)
            logger.info(f"Configuration loaded successfully from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def _load_yaml(self) -> Dict[str, Any]:
        """Load YAML configuration file."""
        config_file = Path(self.config_path)

        if not config_file.exists():
            logger.warning(f"Config file not found at {self.config_path}, using defaults")
            return self._get_defaults()

        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f) or {}
            logger.info(f"Loaded YAML config from {config_file}")
            return config
        except Exception as e:
            logger.error(f"Failed to load YAML config: {e}")
            raise

    def _load_env_overrides(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Override configuration with environment variables."""
        config = base_config.copy()

        # Redis overrides
        if not "redis" in config:
            config["redis"] = {}

        if os.getenv("REDIS_HOST"):
            config["redis"]["host"] = os.getenv("REDIS_HOST")
        if os.getenv("REDIS_PORT"):
            config["redis"]["port"] = int(os.getenv("REDIS_PORT"))
        if os.getenv("REDIS_DB"):
            config["redis"]["db"] = int(os.getenv("REDIS_DB"))
        if os.getenv("REDIS_PASSWORD"):
            config["redis"]["password"] = os.getenv("REDIS_PASSWORD")

        # Kitbash core overrides
        if not "kitbash" in config:
            config["kitbash"] = {}

        if os.getenv("KITBASH_ENVIRONMENT"):
            config["kitbash"]["environment"] = os.getenv("KITBASH_ENVIRONMENT")
        if os.getenv("KITBASH_LOG_LEVEL"):
            config["kitbash"]["log_level"] = os.getenv("KITBASH_LOG_LEVEL")

        # Layer timeout overrides
        if "layers" not in config:
            config["layers"] = {}

        layer_overrides = {
            "LAYER0_TIMEOUT_MS": ("layer0", "timeout_ms"),
            "LAYER1_TIMEOUT_MS": ("layer1", "timeout_ms"),
            "LAYER2_TIMEOUT_MS": ("layer2", "timeout_ms"),
            "LAYER3_TIMEOUT_MS": ("layer3", "timeout_ms"),
            "LAYER4_TIMEOUT_MS": ("layer4", "timeout_ms"),
        }

        for env_var, (layer_name, field) in layer_overrides.items():
            if os.getenv(env_var):
                if layer_name not in config["layers"]:
                    config["layers"][layer_name] = {}
                config["layers"][layer_name][field] = int(os.getenv(env_var))

        # Worker configuration overrides
        if "workers" not in config:
            config["workers"] = {}

        worker_overrides = {
            "BITNET_HOST": ("bitnet", "host"),
            "BITNET_PORT": ("bitnet", "port"),
            "BITNET_ENABLED": ("bitnet", "enabled"),
            "CARTRIDGE_HOST": ("cartridge", "host"),
            "CARTRIDGE_PORT": ("cartridge", "port"),
            "CARTRIDGE_ENABLED": ("cartridge", "enabled"),
            "KOBOLD_HOST": ("kobold", "host"),
            "KOBOLD_PORT": ("kobold", "port"),
            "KOBOLD_ENABLED": ("kobold", "enabled"),
        }

        for env_var, (worker_name, field) in worker_overrides.items():
            if os.getenv(env_var):
                if worker_name not in config["workers"]:
                    config["workers"][worker_name] = {}
                value = os.getenv(env_var)
                if field == "port":
                    value = int(value)
                elif field == "enabled":
                    value = value.lower() in ("true", "1", "yes")
                config["workers"][worker_name][field] = value

        return config

    def _get_defaults(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "redis": {"host": "localhost", "port": 6379, "db": 0},
            "kitbash": {"environment": "development", "log_level": "INFO"},
            "layers": {},
            "workers": {},
            "diagnostics": {},
            "performance": {},
            "redis_keys": {"prefix": "kitbash:"},
        }

    def get(self) -> KitbashConfig:
        """Get the loaded configuration."""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        return self.config

    def redis_config(self) -> RedisConfig:
        """Get Redis configuration."""
        return self.config.redis if self.config else RedisConfig()

    def layer_config(self, layer_name: str) -> Optional[LayerConfig]:
        """Get configuration for a specific layer."""
        if not self.config:
            return None
        return self.config.layers.get(layer_name)

    def worker_config(self, worker_name: str) -> Optional[WorkerConfig]:
        """Get configuration for a specific worker."""
        if not self.config:
            return None
        return self.config.workers.get(worker_name)

    def diagnostics_config(self) -> DiagnosticsConfig:
        """Get diagnostics configuration."""
        return self.config.diagnostics if self.config else DiagnosticsConfig()

    def performance_config(self) -> PerformanceConfig:
        """Get performance configuration."""
        return self.config.performance if self.config else PerformanceConfig()

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary (for logging/debugging)."""
        if not self.config:
            return {}
        return self.config.dict()


def setup_logging(config: Optional[KitbashConfig] = None) -> None:
    """
    Set up logging based on configuration.

    Args:
        config: KitbashConfig object. If None, uses defaults.
    """
    log_level = "INFO"
    if config:
        log_level = config.kitbash.get("log_level", "INFO")

    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


# Singleton instance
_config_loader: Optional[ConfigLoader] = None


def get_config(config_path: Optional[str] = None) -> KitbashConfig:
    """Get or create the global config loader."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_path)
    return _config_loader.get()


if __name__ == "__main__":
    # Test the config loader
    loader = ConfigLoader()
    config = loader.get()
    print("Configuration loaded successfully!")
    print(f"Redis: {config.redis.host}:{config.redis.port}")
    print(f"Environment: {config.kitbash.get('environment')}")
    print(f"Layers: {list(config.layers.keys())}")
