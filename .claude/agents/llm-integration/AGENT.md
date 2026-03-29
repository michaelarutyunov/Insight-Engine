# LLM Integration Agent

## Role

Implements all blocks that call the Anthropic API: Generation, Evaluation, and LLM Flex types. Owns prompt construction, API call patterns, response parsing, and provider abstraction. Also responsible for the chat panel (Phase 3).

---

## Domain Knowledge

### Anthropic API Setup

```python
import anthropic

client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

response = await client.messages.create(
    model=config.get("model", "claude-sonnet-4-6"),
    max_tokens=config.get("max_tokens", 2048),
    messages=[{"role": "user", "content": prompt}],
)
result_text = response.content[0].text
```

Always use `AsyncAnthropic` — blocks run inside an async executor. Never use the sync client.

### Model Configuration

Every LLM block must expose `model` in its `config_schema` with `claude-sonnet-4-6` as the default. This allows per-block model selection without code changes.

```python
@property
def config_schema(self) -> Dict:
    return {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "default": "claude-sonnet-4-6",
                "description": "Anthropic model ID"
            },
            "max_tokens": {"type": "integer", "default": 2048},
            # ... block-specific fields
        },
        "required": [...]
    }
```

### Prompt Construction Pattern

Keep prompt templates as class-level constants, not inline strings. This makes them testable and replaceable:

```python
class PersonaGeneration(GenerationBase):
    SYSTEM_PROMPT = "You are a qualitative researcher..."
    USER_PROMPT_TEMPLATE = """
Given this respondent segment: {segment_profile}
Generate {count} distinct synthetic personas...
"""

    async def execute(self, inputs, config):
        prompt = self.USER_PROMPT_TEMPLATE.format(
            segment_profile=inputs["segment_profile_set"],
            count=config["persona_count"],
        )
        response = await self._call_llm(prompt, config)
        return {"persona_set": self._parse_personas(response)}
```

### Response Parsing

LLM responses must be parsed into typed data objects (defined in `schemas/data_objects.py`). Never return raw strings as block output.

Defensive parsing pattern:
```python
def _parse_personas(self, raw: str) -> list[dict]:
    try:
        # Attempt structured parse (JSON block in response)
        import json, re
        match = re.search(r"```json\n(.*?)\n```", raw, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except (json.JSONDecodeError, AttributeError):
        pass
    # Fallback: return as generic blob with raw text
    return [{"raw": raw, "parse_error": True}]
```

### Testing LLM Blocks

Never make real API calls in tests. Mock at the `client.messages.create` level:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_persona_generation_prompt():
    block = PersonaGeneration()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='```json\n[{"name": "Alice"}]\n```')]

    with patch.object(block, "_call_llm", new=AsyncMock(return_value=mock_response.content[0].text)):
        result = await block.execute(
            inputs={"segment_profile_set": [{"label": "Budget-conscious", "size": 0.3}]},
            config={"persona_count": 1, "model": "claude-sonnet-4-6"},
        )

    assert "persona_set" in result
    assert result["persona_set"][0]["name"] == "Alice"
```

Tests must cover:
1. Prompt construction (assert expected strings appear in the prompt)
2. Response parsing (valid JSON, malformed JSON, empty response)
3. Output schema completeness (all declared output ports present)

---

## Anti-Patterns to Flag

- **Sync Anthropic client**: `anthropic.Anthropic()` instead of `AsyncAnthropic()` — blocks the event loop.
- **Hardcoded model names**: `model="claude-sonnet-4-6"` in `execute()` rather than `config.get("model", "claude-sonnet-4-6")`.
- **Raw string outputs**: Returning `{"output": response_text}` instead of a typed data object.
- **Inline prompt templates**: String literals inside `execute()` instead of class-level constants — untestable.
- **No parse fallback**: Assuming LLM always returns valid JSON — always handle malformed responses.
- **Real API calls in tests**: Any test that hits the actual Anthropic API is slow, expensive, and non-deterministic.

---

## Context Documents

- **`.claude/context/block-contracts.md`** — BlockBase interface; required for all block implementations
- **`.claude/context/data-objects.md`** — typed data object schemas; reference when defining block output types
