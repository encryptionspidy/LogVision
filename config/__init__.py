"""Config package — environment-aware configuration loading."""

from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)


def load_config():
    """
    Load configuration based on ENV environment variable.

    ENV=production -> ProdConfig
    ENV=development (or unset) -> DevConfig
    """
    env = os.environ.get("ENV", "development").lower()

    if env == "production":
        from config.prod import ProdConfig, validate_prod_config
        config = ProdConfig()
        issues = validate_prod_config(config)
        for issue in issues:
            logger.warning("Config: %s", issue)
        return config
    else:
        from config.dev import DevConfig
        config = DevConfig()
        logger.info("Loaded development configuration")
        return config
