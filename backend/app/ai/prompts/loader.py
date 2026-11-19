"""
AI Engine — Prompt Template Loader
==================================

Jinja2-based template loader for Harness Agentic AI system prompts.
"""

import os
import logging
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)


class PromptLoader:
    """Loads and renders AI prompt templates from the prompts directory."""

    def __init__(self):
        self._base_dir = os.path.dirname(os.path.abspath(__file__))
        self._env = Environment(
            loader=FileSystemLoader(self._base_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )

    def render(self, template_path: str, variables: Dict[str, Any] | None = None) -> str:
        """Loads a template from the filesystem and renders it with variables."""
        try:
            template = self._env.get_template(template_path)
            context = variables or {}
            return template.render(**context)
        except TemplateNotFound:
            logger.error(f"AI Prompt template not found: {template_path}")
            raise FileNotFoundError(
                f"Prompt template '{template_path}' not found in {self._base_dir}"
            )
        except Exception as e:
            logger.error(f"Error rendering prompt '{template_path}': {str(e)}")
            raise


loader = PromptLoader()
