"""Research Workflow - Experiment versioning, parameter sweeps, and statistics."""

from .experiment_versioning import (
    # Enums
    ExperimentStatus,
    VersionType,
    DiffType,
    # Models
    SemanticVersion,
    RAGSourceReference,
    ProvenanceMetadata,
    ConfigurationSnapshot,
    ExperimentVersion,
    Experiment,
    ConfigDiff,
    VersionComparison,
    # Service
    ExperimentVersioning,
    get_experiment_versioning,
)

from .parameter_sweep import (
    # Enums
    SweepStatus,
    ParameterType,
    # Models
    ParameterDefinition,
    SweepConfiguration,
    ExperimentResult,
    SweepProgress,
    SweepResults,
    # Service
    ParameterSweepEngine,
    get_parameter_sweep_engine,
)

from .statistical_testing import (
    # Enums
    TestType,
    EffectSizeType,
    SignificanceLevel,
    # Models
    TestResult,
    DescriptiveStats,
    MultipleComparisonResult,
    PowerAnalysisResult,
    # Service
    StatisticalTestingTools,
    get_statistical_testing_tools,
)

__all__ = [
    # Experiment Versioning - Enums
    "ExperimentStatus",
    "VersionType",
    "DiffType",
    # Experiment Versioning - Models
    "SemanticVersion",
    "RAGSourceReference",
    "ProvenanceMetadata",
    "ConfigurationSnapshot",
    "ExperimentVersion",
    "Experiment",
    "ConfigDiff",
    "VersionComparison",
    # Experiment Versioning - Service
    "ExperimentVersioning",
    "get_experiment_versioning",
    # Parameter Sweep - Enums
    "SweepStatus",
    "ParameterType",
    # Parameter Sweep - Models
    "ParameterDefinition",
    "SweepConfiguration",
    "ExperimentResult",
    "SweepProgress",
    "SweepResults",
    # Parameter Sweep - Service
    "ParameterSweepEngine",
    "get_parameter_sweep_engine",
    # Statistical Testing - Enums
    "TestType",
    "EffectSizeType",
    "SignificanceLevel",
    # Statistical Testing - Models
    "TestResult",
    "DescriptiveStats",
    "MultipleComparisonResult",
    "PowerAnalysisResult",
    # Statistical Testing - Service
    "StatisticalTestingTools",
    "get_statistical_testing_tools",
]