"""
Dataset Exporters - CSV, JSON, Parquet, Arrow, and publication export formats.

S15.1: Publication-ready exports for IEEE, ACM, and other academic formats.
S15.5: Publication-quality plots with matplotlib.
S15.7: Jupyter notebook integration for interactive analysis.
S15.11-12: Export configuration wizard and publication preview.
"""

from .publication_exporter import (
    # Main classes
    PublicationExporter,
    ExportConfig,
    ExportResult,
    # Enums
    PublicationFormat,
    ExportFormat,
    TableStyle,
    FigureStyle,
    # Data models
    Citation,
    TableColumn,
    TableData,
    FigureData,
    MethodologySection,
    # Generators
    FormatGenerator,
    LaTeXGenerator,
    MarkdownGenerator,
    # Convenience functions
    create_table_from_dict,
    create_methodology_from_experiment,
    get_publication_exporter,
    initialize_publication_exporter,
)

from .plot_generator import (
    # Main class
    PlotGenerator,
    # Enums
    PlotType,
    ColorScheme,
    PlotFormat,
    # Data models
    PlotStyle,
    PlotData,
    PlotResult,
    # Convenience functions
    create_comparison_plot,
    create_training_curve,
    is_plotting_available,
    get_missing_dependencies,
)

from .jupyter_integration import (
    # Main class
    JupyterIntegration,
    # Enums
    OutputFormat,
    WidgetType,
    # Data models
    DataAccessResult,
    VisualizationConfig,
    NotebookCell,
    NotebookTemplate,
    # Convenience functions
    get_jupyter_integration,
    initialize_jupyter_integration,
)

from .export_wizard import (
    # Main classes
    ExportWizard,
    PublicationPreview,
    # Enums
    WizardStep,
    PreviewFormat,
    ExportTemplate,
    # Data models
    WizardState,
    PreviewResult,
    ValidationResult,
    TemplateConfig,
    # Template configs
    TEMPLATE_CONFIGS,
    # Convenience functions
    get_export_wizard,
    get_publication_preview,
)

__all__ = [
    # Main classes
    "PublicationExporter",
    "ExportConfig",
    "ExportResult",
    # Enums
    "PublicationFormat",
    "ExportFormat",
    "TableStyle",
    "FigureStyle",
    # Data models
    "Citation",
    "TableColumn",
    "TableData",
    "FigureData",
    "MethodologySection",
    # Generators
    "FormatGenerator",
    "LaTeXGenerator",
    "MarkdownGenerator",
    # Convenience functions
    "create_table_from_dict",
    "create_methodology_from_experiment",
    "get_publication_exporter",
    "initialize_publication_exporter",
    # Plot Generator (S15.5)
    "PlotGenerator",
    "PlotType",
    "ColorScheme",
    "PlotFormat",
    "PlotStyle",
    "PlotData",
    "PlotResult",
    "create_comparison_plot",
    "create_training_curve",
    "is_plotting_available",
    "get_missing_dependencies",
    # Jupyter Integration (S15.7)
    "JupyterIntegration",
    "OutputFormat",
    "WidgetType",
    "DataAccessResult",
    "VisualizationConfig",
    "NotebookCell",
    "NotebookTemplate",
    "get_jupyter_integration",
    "initialize_jupyter_integration",
    # Export Wizard (S15.11-12)
    "ExportWizard",
    "PublicationPreview",
    "WizardStep",
    "PreviewFormat",
    "ExportTemplate",
    "WizardState",
    "PreviewResult",
    "ValidationResult",
    "TemplateConfig",
    "TEMPLATE_CONFIGS",
    "get_export_wizard",
    "get_publication_preview",
]
