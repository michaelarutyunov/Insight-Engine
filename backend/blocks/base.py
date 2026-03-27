from abc import ABC, abstractmethod
from typing import Any


class BlockBase(ABC):
    """Abstract base for all blocks in the Insights IDE block library."""

    @property
    @abstractmethod
    def block_type(self) -> str:
        """Abstract category. One of: source, transform, generation, evaluation,
        comparator, reporting, llm_flex, router, hitl, sink."""
        ...

    @property
    @abstractmethod
    def input_schemas(self) -> list[str]:
        """Accepted input data type identifiers. Source blocks return []."""
        ...

    @property
    @abstractmethod
    def output_schemas(self) -> list[str]:
        """Produced output data type identifiers. Sink blocks return []."""
        ...

    @property
    @abstractmethod
    def config_schema(self) -> dict:
        """JSON Schema dict describing valid configuration for this block."""
        ...

    @property
    def description(self) -> str:
        """Natural language description for the block catalog."""
        return ""

    @abstractmethod
    def validate_config(self, config: dict) -> bool:
        """Returns True if the provided config is valid for this block."""
        ...

    @abstractmethod
    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        """Execute this block. Must return all ports declared in output_schemas."""
        ...

    def test_fixtures(self) -> dict:
        """Sample inputs, config, and expected outputs for contract tests."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement test_fixtures()")


class SourceBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "source"

    @property
    def input_schemas(self) -> list[str]:
        return []


class TransformBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "transform"


class GenerationBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "generation"


class EvaluationBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "evaluation"


class ComparatorBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "comparator"


class LLMFlexBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "llm_flex"


class RouterBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "router"

    @abstractmethod
    def resolve_route(self, inputs: dict[str, Any]) -> list[str]:
        """Return list of output edge IDs to activate."""
        ...


class HITLBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "hitl"

    @abstractmethod
    def render_checkpoint(self, inputs: dict[str, Any]) -> dict:
        """Prepare data to present to the human reviewer."""
        ...

    @abstractmethod
    def process_response(self, human_input: dict) -> dict[str, Any]:
        """Handle the human's response and produce the block's output."""
        ...


class ReportingBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "reporting"

    @abstractmethod
    def declare_pipeline_inputs(self) -> list[str]:
        """List of upstream node IDs (not just adjacent) whose outputs are needed."""
        ...


class SinkBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "sink"

    @property
    def output_schemas(self) -> list[str]:
        return []
