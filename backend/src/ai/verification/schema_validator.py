"""
Schema Validator for LLM Outputs.

Validates that LLM-generated JSON/structured outputs conform to
expected schemas. This is critical for preventing hallucinations
where the LLM invents fields or uses incorrect types.
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union

from loguru import logger

from src.ai.verification.verification_pipeline import (
    VerificationCategory,
    VerificationCheck,
    VerificationStatus,
)


class SchemaType(str, Enum):
    """Supported schema types."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"
    ANY = "any"


@dataclass
class SchemaDefinition:
    """Definition of an expected schema."""
    name: str
    schema_type: SchemaType
    required: bool = True
    nullable: bool = False
    properties: dict = field(default_factory=dict)  # For objects
    items: Optional["SchemaDefinition"] = None  # For arrays
    enum_values: list = field(default_factory=list)  # Allowed values
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern for strings
    description: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        result = {
            "name": self.name,
            "type": self.schema_type.value,
            "required": self.required,
            "nullable": self.nullable,
        }
        if self.properties:
            result["properties"] = {
                k: v.to_dict() for k, v in self.properties.items()
            }
        if self.items:
            result["items"] = self.items.to_dict()
        if self.enum_values:
            result["enum"] = self.enum_values
        if self.min_value is not None:
            result["minimum"] = self.min_value
        if self.max_value is not None:
            result["maximum"] = self.max_value
        if self.min_length is not None:
            result["minLength"] = self.min_length
        if self.max_length is not None:
            result["maxLength"] = self.max_length
        if self.pattern:
            result["pattern"] = self.pattern
        return result


@dataclass
class ValidationError:
    """A single validation error."""
    path: str  # JSONPath to the error location
    message: str
    expected: Any
    actual: Any
    severity: str = "error"  # error, warning


class SchemaValidator:
    """
    Validates LLM outputs against predefined schemas.

    Features:
    - JSON structure validation
    - Type checking
    - Range/length constraints
    - Enum validation
    - Nested object/array validation
    - Custom validation rules
    """

    def __init__(self):
        # Registered schemas
        self._schemas: dict[str, SchemaDefinition] = {}

        # Predefined schemas for common outputs
        self._register_builtin_schemas()

        logger.info("SchemaValidator initialized")

    def _register_builtin_schemas(self) -> None:
        """Register built-in schemas for common outputs."""
        # Smart home configuration schema
        self.register_schema(
            "smart_home",
            SchemaDefinition(
                name="smart_home",
                schema_type=SchemaType.OBJECT,
                properties={
                    "home_id": SchemaDefinition(
                        name="home_id",
                        schema_type=SchemaType.STRING,
                        min_length=1,
                    ),
                    "name": SchemaDefinition(
                        name="name",
                        schema_type=SchemaType.STRING,
                        min_length=1,
                        max_length=100,
                    ),
                    "rooms": SchemaDefinition(
                        name="rooms",
                        schema_type=SchemaType.ARRAY,
                        items=SchemaDefinition(
                            name="room",
                            schema_type=SchemaType.OBJECT,
                            properties={
                                "room_id": SchemaDefinition(
                                    name="room_id",
                                    schema_type=SchemaType.STRING,
                                ),
                                "name": SchemaDefinition(
                                    name="name",
                                    schema_type=SchemaType.STRING,
                                ),
                                "type": SchemaDefinition(
                                    name="type",
                                    schema_type=SchemaType.STRING,
                                    enum_values=[
                                        "living_room", "bedroom", "kitchen",
                                        "bathroom", "garage", "office",
                                        "dining_room", "hallway", "basement",
                                        "attic", "laundry", "other",
                                    ],
                                ),
                                "floor": SchemaDefinition(
                                    name="floor",
                                    schema_type=SchemaType.INTEGER,
                                    min_value=-2,
                                    max_value=100,
                                ),
                            },
                        ),
                    ),
                },
            ),
        )

        # Device schema
        self.register_schema(
            "device",
            SchemaDefinition(
                name="device",
                schema_type=SchemaType.OBJECT,
                properties={
                    "device_id": SchemaDefinition(
                        name="device_id",
                        schema_type=SchemaType.STRING,
                        min_length=1,
                    ),
                    "device_type": SchemaDefinition(
                        name="device_type",
                        schema_type=SchemaType.STRING,
                        min_length=1,
                    ),
                    "name": SchemaDefinition(
                        name="name",
                        schema_type=SchemaType.STRING,
                        min_length=1,
                        max_length=100,
                    ),
                    "room_id": SchemaDefinition(
                        name="room_id",
                        schema_type=SchemaType.STRING,
                        required=False,
                        nullable=True,
                    ),
                    "state": SchemaDefinition(
                        name="state",
                        schema_type=SchemaType.OBJECT,
                        required=False,
                    ),
                },
            ),
        )

        # Threat injection schema
        self.register_schema(
            "threat",
            SchemaDefinition(
                name="threat",
                schema_type=SchemaType.OBJECT,
                properties={
                    "threat_id": SchemaDefinition(
                        name="threat_id",
                        schema_type=SchemaType.STRING,
                    ),
                    "threat_type": SchemaDefinition(
                        name="threat_type",
                        schema_type=SchemaType.STRING,
                        enum_values=[
                            "data_exfiltration", "ddos_attack", "camera_hijack",
                            "lock_manipulation", "sensor_spoofing",
                            "command_injection", "replay_attack",
                        ],
                    ),
                    "severity": SchemaDefinition(
                        name="severity",
                        schema_type=SchemaType.STRING,
                        enum_values=["low", "medium", "high", "critical"],
                    ),
                    "target_device_id": SchemaDefinition(
                        name="target_device_id",
                        schema_type=SchemaType.STRING,
                    ),
                },
            ),
        )

        # Agent response schema
        self.register_schema(
            "agent_response",
            SchemaDefinition(
                name="agent_response",
                schema_type=SchemaType.OBJECT,
                properties={
                    "success": SchemaDefinition(
                        name="success",
                        schema_type=SchemaType.BOOLEAN,
                    ),
                    "action": SchemaDefinition(
                        name="action",
                        schema_type=SchemaType.STRING,
                    ),
                    "data": SchemaDefinition(
                        name="data",
                        schema_type=SchemaType.ANY,
                        required=False,
                        nullable=True,
                    ),
                    "error": SchemaDefinition(
                        name="error",
                        schema_type=SchemaType.STRING,
                        required=False,
                        nullable=True,
                    ),
                },
            ),
        )

    def register_schema(self, name: str, schema: SchemaDefinition) -> None:
        """Register a schema for validation."""
        self._schemas[name] = schema
        logger.debug(f"Registered schema: {name}")

    def get_schema(self, name: str) -> Optional[SchemaDefinition]:
        """Get a registered schema."""
        return self._schemas.get(name)

    def validate(
        self,
        data: Any,
        schema_name: str = None,
        schema: SchemaDefinition = None,
    ) -> tuple[bool, list[ValidationError]]:
        """
        Validate data against a schema.

        Args:
            data: The data to validate
            schema_name: Name of a registered schema
            schema: Direct schema definition (overrides schema_name)

        Returns:
            Tuple of (is_valid: bool, errors: list[ValidationError])
        """
        if schema is None:
            if schema_name is None:
                return True, []  # No schema to validate against
            schema = self._schemas.get(schema_name)
            if schema is None:
                return True, []  # Unknown schema, skip validation

        errors = []
        self._validate_value(data, schema, "$", errors)

        return len(errors) == 0, errors

    def _validate_value(
        self,
        value: Any,
        schema: SchemaDefinition,
        path: str,
        errors: list[ValidationError],
    ) -> None:
        """Recursively validate a value against a schema."""
        # Handle null values
        if value is None:
            if schema.nullable or not schema.required:
                return
            else:
                errors.append(ValidationError(
                    path=path,
                    message="Value cannot be null",
                    expected="non-null",
                    actual=None,
                ))
                return

        # Type checking
        actual_type = self._get_type(value)
        if schema.schema_type != SchemaType.ANY:
            if not self._types_match(actual_type, schema.schema_type):
                errors.append(ValidationError(
                    path=path,
                    message=f"Type mismatch",
                    expected=schema.schema_type.value,
                    actual=actual_type.value if actual_type else "unknown",
                ))
                return

        # Type-specific validation
        if schema.schema_type == SchemaType.STRING:
            self._validate_string(value, schema, path, errors)
        elif schema.schema_type == SchemaType.INTEGER:
            self._validate_number(value, schema, path, errors, integer=True)
        elif schema.schema_type == SchemaType.NUMBER:
            self._validate_number(value, schema, path, errors, integer=False)
        elif schema.schema_type == SchemaType.ARRAY:
            self._validate_array(value, schema, path, errors)
        elif schema.schema_type == SchemaType.OBJECT:
            self._validate_object(value, schema, path, errors)

        # Enum validation
        if schema.enum_values and value not in schema.enum_values:
            errors.append(ValidationError(
                path=path,
                message="Value not in allowed enum",
                expected=schema.enum_values,
                actual=value,
            ))

    def _get_type(self, value: Any) -> Optional[SchemaType]:
        """Determine the schema type of a value."""
        if value is None:
            return SchemaType.NULL
        elif isinstance(value, bool):
            return SchemaType.BOOLEAN
        elif isinstance(value, int):
            return SchemaType.INTEGER
        elif isinstance(value, float):
            return SchemaType.NUMBER
        elif isinstance(value, str):
            return SchemaType.STRING
        elif isinstance(value, list):
            return SchemaType.ARRAY
        elif isinstance(value, dict):
            return SchemaType.OBJECT
        return None

    def _types_match(
        self, actual: Optional[SchemaType], expected: SchemaType
    ) -> bool:
        """Check if types match (with some flexibility)."""
        if actual == expected:
            return True
        # Allow integer where number is expected
        if expected == SchemaType.NUMBER and actual == SchemaType.INTEGER:
            return True
        return False

    def _validate_string(
        self,
        value: str,
        schema: SchemaDefinition,
        path: str,
        errors: list[ValidationError],
    ) -> None:
        """Validate string constraints."""
        if schema.min_length is not None and len(value) < schema.min_length:
            errors.append(ValidationError(
                path=path,
                message=f"String too short (min: {schema.min_length})",
                expected=f">= {schema.min_length} chars",
                actual=len(value),
            ))

        if schema.max_length is not None and len(value) > schema.max_length:
            errors.append(ValidationError(
                path=path,
                message=f"String too long (max: {schema.max_length})",
                expected=f"<= {schema.max_length} chars",
                actual=len(value),
            ))

        if schema.pattern:
            if not re.match(schema.pattern, value):
                errors.append(ValidationError(
                    path=path,
                    message="String does not match pattern",
                    expected=schema.pattern,
                    actual=value,
                ))

    def _validate_number(
        self,
        value: Union[int, float],
        schema: SchemaDefinition,
        path: str,
        errors: list[ValidationError],
        integer: bool = False,
    ) -> None:
        """Validate number constraints."""
        if integer and not isinstance(value, int):
            errors.append(ValidationError(
                path=path,
                message="Expected integer",
                expected="integer",
                actual=type(value).__name__,
            ))

        if schema.min_value is not None and value < schema.min_value:
            errors.append(ValidationError(
                path=path,
                message=f"Value below minimum ({schema.min_value})",
                expected=f">= {schema.min_value}",
                actual=value,
            ))

        if schema.max_value is not None and value > schema.max_value:
            errors.append(ValidationError(
                path=path,
                message=f"Value above maximum ({schema.max_value})",
                expected=f"<= {schema.max_value}",
                actual=value,
            ))

    def _validate_array(
        self,
        value: list,
        schema: SchemaDefinition,
        path: str,
        errors: list[ValidationError],
    ) -> None:
        """Validate array and its items."""
        if schema.min_length is not None and len(value) < schema.min_length:
            errors.append(ValidationError(
                path=path,
                message=f"Array too short (min: {schema.min_length})",
                expected=f">= {schema.min_length} items",
                actual=len(value),
            ))

        if schema.max_length is not None and len(value) > schema.max_length:
            errors.append(ValidationError(
                path=path,
                message=f"Array too long (max: {schema.max_length})",
                expected=f"<= {schema.max_length} items",
                actual=len(value),
            ))

        # Validate items if schema provided
        if schema.items:
            for i, item in enumerate(value):
                self._validate_value(item, schema.items, f"{path}[{i}]", errors)

    def _validate_object(
        self,
        value: dict,
        schema: SchemaDefinition,
        path: str,
        errors: list[ValidationError],
    ) -> None:
        """Validate object properties."""
        if not schema.properties:
            return  # No property constraints

        # Check required properties
        for prop_name, prop_schema in schema.properties.items():
            if prop_schema.required and prop_name not in value:
                errors.append(ValidationError(
                    path=f"{path}.{prop_name}",
                    message="Required property missing",
                    expected="present",
                    actual="missing",
                ))
            elif prop_name in value:
                # Validate property value
                self._validate_value(
                    value[prop_name],
                    prop_schema,
                    f"{path}.{prop_name}",
                    errors,
                )

    def create_verifier(
        self, schema_name: str
    ) -> callable:
        """
        Create a verifier function for the verification pipeline.

        Args:
            schema_name: Name of the schema to validate against

        Returns:
            Async verifier function compatible with VerificationPipeline
        """
        schema = self._schemas.get(schema_name)

        async def verifier(data: Any, context: dict) -> VerificationCheck:
            # Try to parse JSON if string
            parsed_data = data
            if isinstance(data, str):
                try:
                    parsed_data = json.loads(data)
                except json.JSONDecodeError:
                    return VerificationCheck.create(
                        category=VerificationCategory.SCHEMA,
                        name=f"schema_validation_{schema_name}",
                        status=VerificationStatus.REJECT,
                        confidence=1.0,
                        message="Invalid JSON format",
                        details={"raw_data": data[:500] if len(data) > 500 else data},
                    )

            is_valid, errors = self.validate(parsed_data, schema=schema)

            if is_valid:
                return VerificationCheck.create(
                    category=VerificationCategory.SCHEMA,
                    name=f"schema_validation_{schema_name}",
                    status=VerificationStatus.PASS,
                    confidence=1.0,
                    message="Schema validation passed",
                )
            else:
                error_details = [
                    {"path": e.path, "message": e.message, "expected": str(e.expected)}
                    for e in errors[:5]  # Limit to first 5 errors
                ]
                return VerificationCheck.create(
                    category=VerificationCategory.SCHEMA,
                    name=f"schema_validation_{schema_name}",
                    status=VerificationStatus.REJECT,
                    confidence=1.0,
                    message=f"Schema validation failed: {len(errors)} error(s)",
                    details={"errors": error_details},
                )

        return verifier

    def validate_json_response(
        self, json_str: str, schema_name: str
    ) -> tuple[bool, Any, list[ValidationError]]:
        """
        Parse and validate a JSON response.

        Args:
            json_str: JSON string to parse and validate
            schema_name: Schema to validate against

        Returns:
            Tuple of (is_valid, parsed_data, errors)
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return False, None, [ValidationError(
                path="$",
                message=f"JSON parse error: {str(e)}",
                expected="valid JSON",
                actual=json_str[:100],
            )]

        is_valid, errors = self.validate(data, schema_name=schema_name)
        return is_valid, data, errors


# Global instance
_schema_validator: Optional[SchemaValidator] = None


def get_schema_validator() -> SchemaValidator:
    """Get or create the global schema validator."""
    global _schema_validator
    if _schema_validator is None:
        _schema_validator = SchemaValidator()
    return _schema_validator
