"""Discussion Guide block — LLM-powered discussion guide generation from respondent data."""

from typing import Any

from blocks._llm_client import BlockExecutionError, call_llm
from blocks.base import GenerationBase


class DiscussionGuide(GenerationBase):
    """Generates structured discussion guides for qualitative research interviews using an LLM."""

    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["text_corpus"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "research_objectives": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "List of research objectives and topics to explore in the interview",
                },
                "interview_type": {
                    "type": "string",
                    "enum": ["idi", "focus_group", "online"],
                    "default": "idi",
                    "description": "Interview methodology: idi (in-depth interview), focus_group, or online survey",
                },
                "duration_minutes": {
                    "type": "integer",
                    "default": 60,
                    "minimum": 15,
                    "maximum": 180,
                    "description": "Target interview duration in minutes",
                },
                "model": {
                    "type": "string",
                    "default": "claude-sonnet-4-6",
                    "description": "LLM model identifier",
                },
                "temperature": {
                    "type": "number",
                    "default": 0.5,
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Sampling temperature for creativity control",
                },
                "seed": {
                    "type": "integer",
                    "description": "Optional seed for reproducibility tracking",
                },
            },
            "required": ["research_objectives"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return "Generates structured discussion guides for qualitative research interviews from respondent data using a language model. Use this block to create interviewer guides with open-ended questions, probing techniques, and timing allocations based on research objectives and respondent characteristics. Supports in-depth interviews (IDI), focus groups, and online qualitative methodologies."

    @property
    def methodological_notes(self) -> str:
        return "Non-deterministic LLM-powered generation — outputs vary with temperature, seed, and model version. Track these parameters for reproducibility. Quality depends heavily on research_objectives specificity — provide clear, actionable goals for the interview. The respondent_collection input should contain relevant demographic, psychographic, or behavioral data to tailor questions. Generated guides include section timing, question phrasing, and probing prompts. Review and refine outputs before field deployment to ensure alignment with research standards and respondent experience goals."

    @property
    def tags(self) -> list[str]:
        return [
            "llm",
            "generation",
            "qualitative",
            "interview",
            "discussion-guide",
            "moderation",
            "research-design",
            "non-deterministic",
        ]

    def validate_config(self, config: dict) -> bool:
        """Validate configuration against schema requirements."""
        # Check required field
        if "research_objectives" not in config:
            return False

        objectives = config["research_objectives"]
        if not isinstance(objectives, list):
            return False
        if len(objectives) < 1:
            return False
        if not all(isinstance(obj, str) and obj.strip() for obj in objectives):
            return False

        # Validate interview_type if provided
        if "interview_type" in config:
            interview_type = config["interview_type"]
            if not isinstance(interview_type, str):
                return False
            if interview_type not in ["idi", "focus_group", "online"]:
                return False

        # Validate duration_minutes if provided
        if "duration_minutes" in config:
            duration = config["duration_minutes"]
            if not isinstance(duration, int):
                return False
            if duration < 15 or duration > 180:
                return False

        # Validate temperature if provided
        if "temperature" in config:
            temp = config["temperature"]
            if not isinstance(temp, (int, float)) or temp < 0.0 or temp > 1.0:
                return False

        # Validate model if provided
        if "model" in config and (
            not isinstance(config["model"], str) or not config["model"].strip()
        ):
            return False

        # Validate seed if provided
        return not ("seed" in config and not isinstance(config["seed"], int))

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        """Generate discussion guide from respondent data using LLM."""
        # Extract respondent collection
        collection = inputs["respondent_collection"]
        rows = collection.get("rows", collection) if isinstance(collection, dict) else collection

        # Build prompts
        system_prompt = """You are an expert qualitative researcher and moderator. Your task is to generate a structured discussion guide for research interviews based on research objectives and respondent data.

The discussion guide must include:
1. Introduction/Opening: How to welcome respondents and set expectations
2. Research Questions: Main questions organized by topic area, with timing allocations
3. Probing Prompts: Follow-up questions to deepen responses
4. Closing: How to wrap up the interview professionally

Format the guide as a structured document with clear sections, question numbering, and time allocations. Use professional qualitative research terminology and techniques."""

        # Format research objectives
        objectives_list = "\n".join(f"- {obj}" for obj in config["research_objectives"])

        # Build user prompt
        interview_type = config.get("interview_type", "idi")
        duration = config.get("duration_minutes", 60)

        user_prompt = f"""Generate a discussion guide for a {interview_type.upper()} interview ({duration} minutes).

Research Objectives:
{objectives_list}

Respondent Data:
{rows}

Please create a comprehensive discussion guide that addresses these research objectives while being appropriate for the respondent characteristics shown in the data."""

        # Call LLM
        try:
            guide_text = await call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=config.get("model", "claude-sonnet-4-6"),
                temperature=config.get("temperature", 0.5),
                max_tokens=4096,
            )
        except BlockExecutionError as e:
            raise BlockExecutionError(f"Discussion guide generation failed: {e}") from e

        # Validate response
        if not isinstance(guide_text, str):
            raise BlockExecutionError("LLM response is not a string")

        if not guide_text.strip():
            raise BlockExecutionError("LLM returned empty discussion guide")

        return {"text_corpus": {"documents": [guide_text]}}

    def test_fixtures(self) -> dict:
        """Provide test fixtures for contract testing."""
        return {
            "config": {
                "research_objectives": [
                    "Understand unmet needs in home office furniture",
                    "Explore pain points with current setups",
                    "Identify decision criteria for furniture purchases",
                ],
                "interview_type": "idi",
                "duration_minutes": 60,
                "model": "claude-sonnet-4-6",
                "temperature": 0.5,
                "seed": 42,
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [
                        {
                            "respondent_id": "r1",
                            "age": "35-44",
                            "work_from_home_days": 5,
                            "current_setup": "Basic desk and chair",
                            "pain_points": ["Back pain", "Clutter", "Poor lighting"],
                        },
                        {
                            "respondent_id": "r2",
                            "age": "25-34",
                            "work_from_home_days": 3,
                            "current_setup": "Kitchen table",
                            "pain_points": ["No dedicated space", "Uncomfortable", "Distractions"],
                        },
                    ],
                },
            },
            "expected_output": {
                "text_corpus": {
                    "documents": [
                        """# Discussion Guide: Home Office Furniture Research

## Interview Details
- **Methodology**: In-Depth Interview (IDI)
- **Duration**: 60 minutes
- **Target**: Home office workers

---

## I. Introduction & Warm-Up (5 minutes)

**Moderator Opening:**
"Thank you for joining today. I'm here to learn about your experience working from home, specifically your current workspace setup. There are no right or wrong answers — I'm interested in your honest perspectives and experiences."

**Consent & Logistics:**
- Confirm recording permission
- Explain confidentiality
- Outline approximate duration

**Icebreaker:**
"Let's start with a simple question: Can you describe your current workspace in one sentence?"

---

## II. Current Setup Exploration (15 minutes)

**Q1: Workspace Tour**
"Take me through your current home office setup. What does it look like? Where is it located in your home?"

**Probes:**
- How long have you had this setup?
- What led you to this arrangement?
- How did you acquire your current furniture?

**Q2: Daily Experience**
"Walk me through a typical workday in your current space. What works well? What doesn't?"

**Probes:**
- Physical comfort throughout the day
- Ability to focus and concentrate
- Impact on productivity or mood

---

## III. Pain Points & Unmet Needs (20 minutes)

**Q3: Frustrations**
"What aspects of your current workspace frustrate you the most?"

**Probes:**
- Specific incidents or examples
- Workarounds you've developed
- Impact on work quality or well-being

**Q4: Ideal Scenario**
"If you could wave a magic wand and change anything about your workspace, what would you change?"

**Probes:**
- Prioritization among multiple desires
- Constraints preventing these changes
- Trade-offs you'd consider

---

## IV. Purchase Behavior & Decision Criteria (15 minutes)

**Q5: Previous Purchases**
"Tell me about the last time you purchased furniture or equipment for your home office."

**Probes:**
- Research process
- Information sources consulted
- Budget considerations

**Q6: Future Considerations**
"What would matter most to you when selecting new home office furniture?"

**Probes:**
- Feature priorities
- Brand perceptions
- Price sensitivity vs. quality expectations

---

## V. Closing (5 minutes)

**Q7: Final Thoughts**
"Is there anything about your home office experience we haven't discussed that you think is important?"

**Thank You & Next Steps**
- Express appreciation
- Explain how feedback will be used
- Provide contact information for follow-up questions

---

## Moderator Notes:
- Watch for non-verbal cues (shifting, discomfort)
- Allow silence for respondent reflection
- Adapt question order based on natural flow
- Document unexpected insights or themes"""
                    ]
                }
            },
        }
