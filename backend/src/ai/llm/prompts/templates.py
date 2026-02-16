"""
Prompt Templates for Smart-HES Agent Framework.

Uses Jinja2 for flexible prompt generation with:
- Anti-hallucination instructions
- Task-specific prompts for each agent
- JSON output formatting
- RAG context integration
"""

from dataclasses import dataclass
from typing import Any, Optional

from jinja2 import Environment, BaseLoader
from loguru import logger


# Base system prompt for all agents - emphasizes research integrity
BASE_SYSTEM_PROMPT = """You are an AI assistant for the Smart-HES (Smart Home Environment Simulator) Agent Framework,
designed for IEEE IoT Journal and IEEE TDSC research publications.

## Core Principles
1. **Research Integrity**: Only provide information you are confident about
2. **Source Citation**: Always cite sources when using retrieved knowledge
3. **Uncertainty Acknowledgment**: Clearly state when you don't have enough information
4. **No Fabrication**: Never make up device specifications, protocols, or security data

## Anti-Hallucination Rules
- If asked about specific device specifications, only use provided context
- If no relevant context is available, say "I don't have verified information about this"
- When uncertain, express uncertainty rather than guessing
- For numerical values (temperatures, power consumption, etc.), only use verified data

## Response Format
- Be concise and precise
- Use structured formats (lists, tables) when appropriate
- Include confidence indicators when relevant
"""


# Agent-specific prompts
AGENT_PROMPTS = {
    "home_builder": """You are the Home Builder Agent responsible for creating smart home configurations.

## Your Responsibilities
- Generate realistic smart home layouts based on user requirements
- Place devices appropriately in rooms based on device type and room function
- Create inhabitant profiles with realistic schedules
- Ensure configurations match real-world smart home statistics

## Device Placement Rules
- Security cameras: Entry points, exterior, high-value areas
- Motion sensors: Hallways, staircases, entry points
- Thermostats: Living areas, bedrooms (one per zone)
- Smart lights: All rooms with appropriate counts
- Smart locks: Entry doors only
- Smoke detectors: Every bedroom, kitchen, each floor
- Water leak sensors: Bathrooms, kitchen, laundry, near water heaters

## Output Requirements
When generating home configurations:
1. Validate that device counts are realistic
2. Ensure room assignments are appropriate
3. Include only devices from the supported device types
4. Generate valid inhabitant schedules
""",

    "device_manager": """You are the Device Manager Agent responsible for IoT device operations.

## Your Responsibilities
- Manage device states and configurations
- Simulate realistic device behaviors
- Track device data generation
- Monitor device health and status

## Device State Management
- Ensure state transitions are valid for each device type
- Generate realistic telemetry data patterns
- Simulate proper response times for device commands
- Track energy consumption patterns

## Supported Device Types
{device_types}

## Output Requirements
When managing devices:
1. Use only valid device states for each type
2. Generate data within realistic ranges
3. Ensure proper protocol simulation
4. Track all state changes with timestamps
""",

    "threat_injector": """You are the Threat Injector Agent responsible for security scenario simulation.

## Your Responsibilities
- Inject realistic security threats into simulations
- Generate ground truth labels for attack detection research
- Create multi-stage attack timelines
- Simulate various threat categories

## Threat Categories
1. **Data Exfiltration**: Unauthorized data transfer from devices
2. **Device Tampering**: Physical or logical device manipulation
3. **Energy Theft**: Manipulation of power consumption data
4. **DDoS Attack**: Overwhelming devices with traffic
5. **Camera Hijack**: Unauthorized access to video feeds
6. **Man-in-the-Middle**: Intercepting device communications
7. **Replay Attack**: Replaying captured commands

## Attack Severity Levels
- LOW: Minimal impact, easily detectable
- MEDIUM: Moderate impact, requires attention
- HIGH: Significant impact, immediate response needed
- CRITICAL: System-wide impact, emergency response

## Output Requirements
When injecting threats:
1. Ensure attack patterns match known CVEs when referenced
2. Generate accurate ground truth labels
3. Create realistic attack timelines
4. Document all injected anomalies
""",

    "conversation": """You are the conversational AI interface for the Smart-HES Agent Framework.

## Your Role
- Help users build smart home simulations through natural language
- Answer questions about IoT security and device behaviors
- Guide users through research workflows
- Provide clear explanations of simulation results

## Conversation Guidelines
- Be helpful and precise
- Ask clarifying questions when requirements are unclear
- Suggest realistic configurations based on user needs
- Explain technical concepts in accessible terms

## Available Actions
You can help users:
1. Create new smart home configurations
2. Add/remove devices from homes
3. Configure inhabitant behaviors
4. Set up threat injection scenarios
5. Run simulations and view results
6. Export data for research

When unsure about a request, ask for clarification rather than guessing.
""",
}


# JSON output templates
JSON_TEMPLATES = {
    "home_config": {
        "type": "object",
        "required": ["name", "home_type", "rooms", "devices"],
        "properties": {
            "name": {"type": "string"},
            "home_type": {"type": "string", "enum": ["studio", "one_bedroom", "two_bedroom", "family_house", "smart_mansion"]},
            "rooms": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "room_type"],
                    "properties": {
                        "name": {"type": "string"},
                        "room_type": {"type": "string"},
                        "floor": {"type": "integer"},
                    }
                }
            },
            "devices": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["device_type", "room"],
                    "properties": {
                        "device_type": {"type": "string"},
                        "room": {"type": "string"},
                        "name": {"type": "string"},
                    }
                }
            },
            "inhabitants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                        "occupation": {"type": "string"},
                    }
                }
            }
        }
    },

    "threat_config": {
        "type": "object",
        "required": ["threat_type", "target_devices", "severity"],
        "properties": {
            "threat_type": {"type": "string"},
            "target_devices": {"type": "array", "items": {"type": "string"}},
            "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
            "start_time": {"type": "string", "format": "date-time"},
            "duration_seconds": {"type": "integer"},
            "attack_phases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "phase_name": {"type": "string"},
                        "description": {"type": "string"},
                        "duration_seconds": {"type": "integer"},
                    }
                }
            }
        }
    },

    "device_command": {
        "type": "object",
        "required": ["action", "device_id"],
        "properties": {
            "action": {"type": "string"},
            "device_id": {"type": "string"},
            "parameters": {"type": "object"},
        }
    },
}


@dataclass
class PromptTemplate:
    """A prompt template with metadata."""
    name: str
    template: str
    description: str = ""
    required_vars: list[str] = None

    def __post_init__(self):
        if self.required_vars is None:
            self.required_vars = []


class PromptManager:
    """
    Manages prompt templates for the Smart-HES Agent Framework.

    Features:
    - Jinja2 template rendering
    - Agent-specific prompts
    - JSON schema integration
    - Anti-hallucination prompt augmentation
    """

    def __init__(self):
        self.env = Environment(loader=BaseLoader())
        self._templates: dict[str, PromptTemplate] = {}
        self._init_default_templates()
        logger.info("PromptManager initialized with default templates")

    def _init_default_templates(self):
        """Initialize default prompt templates."""
        # Register agent prompts
        for name, content in AGENT_PROMPTS.items():
            self.register_template(
                name=f"agent_{name}",
                template=content,
                description=f"System prompt for {name} agent",
            )

        # Register base prompt
        self.register_template(
            name="base_system",
            template=BASE_SYSTEM_PROMPT,
            description="Base system prompt with anti-hallucination rules",
        )

    def register_template(
        self,
        name: str,
        template: str,
        description: str = "",
        required_vars: list[str] = None,
    ) -> None:
        """Register a new prompt template."""
        self._templates[name] = PromptTemplate(
            name=name,
            template=template,
            description=description,
            required_vars=required_vars or [],
        )

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """Get a template by name."""
        return self._templates.get(name)

    def render(self, name: str, **kwargs) -> str:
        """
        Render a template with variables.

        Args:
            name: Template name
            **kwargs: Template variables

        Returns:
            Rendered template string
        """
        template = self._templates.get(name)
        if not template:
            raise ValueError(f"Template '{name}' not found")

        jinja_template = self.env.from_string(template.template)
        return jinja_template.render(**kwargs)

    def render_string(self, template_str: str, **kwargs) -> str:
        """Render an arbitrary template string."""
        jinja_template = self.env.from_string(template_str)
        return jinja_template.render(**kwargs)

    def get_agent_prompt(self, agent_type: str, **kwargs) -> str:
        """
        Get the system prompt for a specific agent type.

        Args:
            agent_type: Agent type (home_builder, device_manager, threat_injector, conversation)
            **kwargs: Additional variables for the template

        Returns:
            Complete system prompt including base and agent-specific parts
        """
        # Start with base system prompt
        base = self.render("base_system")

        # Add agent-specific prompt
        agent_key = f"agent_{agent_type}"
        if agent_key in self._templates:
            agent_prompt = self.render(agent_key, **kwargs)
            return f"{base}\n\n{agent_prompt}"

        return base

    def get_json_schema(self, schema_name: str) -> dict:
        """Get a JSON schema for structured output."""
        return JSON_TEMPLATES.get(schema_name, {})

    def build_json_prompt(
        self,
        task_description: str,
        schema_name: str,
        context: str = "",
    ) -> str:
        """
        Build a prompt for JSON output generation.

        Args:
            task_description: What the LLM should generate
            schema_name: Name of the JSON schema to use
            context: Additional context

        Returns:
            Formatted prompt for JSON generation
        """
        schema = self.get_json_schema(schema_name)
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found")

        import json
        schema_str = json.dumps(schema, indent=2)

        prompt_parts = [
            f"Task: {task_description}",
            "",
            "You must respond with valid JSON matching this schema:",
            "```json",
            schema_str,
            "```",
        ]

        if context:
            prompt_parts.insert(1, f"\nContext: {context}\n")

        prompt_parts.extend([
            "",
            "IMPORTANT:",
            "- Output ONLY valid JSON, no other text",
            "- Do not wrap in markdown code blocks",
            "- Ensure all required fields are present",
            "- Use realistic values based on the context",
        ])

        return "\n".join(prompt_parts)

    def list_templates(self) -> list[dict]:
        """List all available templates."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "required_vars": t.required_vars,
            }
            for t in self._templates.values()
        ]


# Global instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get or create the global prompt manager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
