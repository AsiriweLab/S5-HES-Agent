"""
Export Configuration Wizard and Publication Preview (S15.11-12).

Provides:
- Interactive export configuration wizard
- Publication preview generation
- Format validation and recommendations
- Template-based export profiles
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from .publication_exporter import (
    PublicationExporter,
    ExportConfig,
    ExportFormat,
    PublicationFormat,
    TableStyle,
    FigureStyle,
    TableData,
    TableColumn,
    FigureData,
    MethodologySection,
    Citation,
)


# =============================================================================
# Enumerations
# =============================================================================


class WizardStep(str, Enum):
    """Wizard navigation steps."""
    FORMAT_SELECTION = "format_selection"
    CONTENT_SELECTION = "content_selection"
    STYLE_CONFIGURATION = "style_configuration"
    METADATA_ENTRY = "metadata_entry"
    PREVIEW = "preview"
    EXPORT = "export"


class PreviewFormat(str, Enum):
    """Preview output formats."""
    HTML = "html"
    TEXT = "text"
    JSON = "json"


class ExportTemplate(str, Enum):
    """Pre-configured export templates."""
    IEEE_JOURNAL = "ieee_journal"
    IEEE_CONFERENCE = "ieee_conference"
    ACM_JOURNAL = "acm_journal"
    ACM_CONFERENCE = "acm_conference"
    ARXIV = "arxiv"
    THESIS = "thesis"
    CUSTOM = "custom"


# =============================================================================
# Data Models
# =============================================================================


class WizardState(BaseModel):
    """Current state of the export wizard."""
    wizard_id: str = Field(default_factory=lambda: str(uuid4()))
    current_step: WizardStep = WizardStep.FORMAT_SELECTION
    completed_steps: list[WizardStep] = Field(default_factory=list)

    # Selected options
    publication_format: Optional[PublicationFormat] = None
    export_format: Optional[ExportFormat] = None
    template: Optional[ExportTemplate] = None

    # Content selections
    include_tables: bool = True
    include_figures: bool = True
    include_methodology: bool = True
    include_citations: bool = True
    include_results: bool = True

    # Style options
    table_style: TableStyle = TableStyle.IEEE_STANDARD
    figure_style: FigureStyle = FigureStyle.IEEE_SINGLE_COLUMN
    figure_dpi: int = 300

    # Metadata
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)

    # Data references
    tables: list[TableData] = Field(default_factory=list)
    figures: list[FigureData] = Field(default_factory=list)
    methodology: Optional[MethodologySection] = None
    citations: list[Citation] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)


class PreviewResult(BaseModel):
    """Result of preview generation."""
    success: bool
    preview_format: PreviewFormat
    content: str
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    estimated_pages: int = 0
    word_count: int = 0


class ValidationResult(BaseModel):
    """Result of configuration validation."""
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class TemplateConfig(BaseModel):
    """Configuration for export templates."""
    template_id: ExportTemplate
    name: str
    description: str
    publication_format: PublicationFormat
    export_format: ExportFormat
    table_style: TableStyle
    figure_style: FigureStyle
    figure_dpi: int
    page_width_inches: float
    column_count: int
    recommended_figure_width: str


# =============================================================================
# Template Definitions
# =============================================================================


TEMPLATE_CONFIGS: dict[ExportTemplate, TemplateConfig] = {
    ExportTemplate.IEEE_JOURNAL: TemplateConfig(
        template_id=ExportTemplate.IEEE_JOURNAL,
        name="IEEE Journal",
        description="IEEE Transactions format (double column)",
        publication_format=PublicationFormat.IEEE,
        export_format=ExportFormat.LATEX,
        table_style=TableStyle.IEEE_STANDARD,
        figure_style=FigureStyle.IEEE_DOUBLE_COLUMN,
        figure_dpi=300,
        page_width_inches=7.0,
        column_count=2,
        recommended_figure_width=r"\columnwidth",
    ),
    ExportTemplate.IEEE_CONFERENCE: TemplateConfig(
        template_id=ExportTemplate.IEEE_CONFERENCE,
        name="IEEE Conference",
        description="IEEE Conference format (double column)",
        publication_format=PublicationFormat.IEEE,
        export_format=ExportFormat.LATEX,
        table_style=TableStyle.IEEE_STANDARD,
        figure_style=FigureStyle.IEEE_SINGLE_COLUMN,
        figure_dpi=300,
        page_width_inches=7.0,
        column_count=2,
        recommended_figure_width=r"\columnwidth",
    ),
    ExportTemplate.ACM_JOURNAL: TemplateConfig(
        template_id=ExportTemplate.ACM_JOURNAL,
        name="ACM Journal",
        description="ACM journal article format",
        publication_format=PublicationFormat.ACM,
        export_format=ExportFormat.LATEX,
        table_style=TableStyle.BOOKTABS,
        figure_style=FigureStyle.ACM_STANDARD,
        figure_dpi=300,
        page_width_inches=6.75,
        column_count=2,
        recommended_figure_width=r"\columnwidth",
    ),
    ExportTemplate.ACM_CONFERENCE: TemplateConfig(
        template_id=ExportTemplate.ACM_CONFERENCE,
        name="ACM Conference",
        description="ACM conference proceedings format",
        publication_format=PublicationFormat.ACM,
        export_format=ExportFormat.LATEX,
        table_style=TableStyle.BOOKTABS,
        figure_style=FigureStyle.ACM_STANDARD,
        figure_dpi=300,
        page_width_inches=6.75,
        column_count=2,
        recommended_figure_width=r"\columnwidth",
    ),
    ExportTemplate.ARXIV: TemplateConfig(
        template_id=ExportTemplate.ARXIV,
        name="arXiv Preprint",
        description="arXiv preprint format (single column)",
        publication_format=PublicationFormat.GENERIC,
        export_format=ExportFormat.LATEX,
        table_style=TableStyle.BOOKTABS,
        figure_style=FigureStyle.IEEE_DOUBLE_COLUMN,
        figure_dpi=300,
        page_width_inches=6.5,
        column_count=1,
        recommended_figure_width=r"\textwidth",
    ),
    ExportTemplate.THESIS: TemplateConfig(
        template_id=ExportTemplate.THESIS,
        name="Thesis/Dissertation",
        description="Academic thesis format (single column)",
        publication_format=PublicationFormat.GENERIC,
        export_format=ExportFormat.LATEX,
        table_style=TableStyle.BOOKTABS,
        figure_style=FigureStyle.IEEE_DOUBLE_COLUMN,
        figure_dpi=300,
        page_width_inches=6.0,
        column_count=1,
        recommended_figure_width=r"0.8\textwidth",
    ),
    ExportTemplate.CUSTOM: TemplateConfig(
        template_id=ExportTemplate.CUSTOM,
        name="Custom",
        description="Custom export configuration",
        publication_format=PublicationFormat.GENERIC,
        export_format=ExportFormat.LATEX,
        table_style=TableStyle.SIMPLE,
        figure_style=FigureStyle.IEEE_SINGLE_COLUMN,
        figure_dpi=300,
        page_width_inches=6.5,
        column_count=1,
        recommended_figure_width=r"\textwidth",
    ),
}


# =============================================================================
# Export Wizard
# =============================================================================


class ExportWizard:
    """
    Interactive export configuration wizard.

    S15.11: Guides users through export configuration with
    validation, recommendations, and preview.
    """

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize export wizard.

        Args:
            output_dir: Directory for exports
        """
        self.output_dir = Path(output_dir or "exports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._state: Optional[WizardState] = None
        self._exporter: Optional[PublicationExporter] = None

    def start_wizard(self, template: Optional[ExportTemplate] = None) -> WizardState:
        """
        Start a new export wizard session.

        Args:
            template: Optional template to pre-configure

        Returns:
            Initial wizard state
        """
        self._state = WizardState()

        if template and template in TEMPLATE_CONFIGS:
            self._apply_template(template)

        return self._state

    def _apply_template(self, template: ExportTemplate) -> None:
        """Apply a template configuration to the wizard state."""
        if self._state is None:
            return

        config = TEMPLATE_CONFIGS[template]
        self._state.template = template
        self._state.publication_format = config.publication_format
        self._state.export_format = config.export_format
        self._state.table_style = config.table_style
        self._state.figure_style = config.figure_style
        self._state.figure_dpi = config.figure_dpi

    def get_state(self) -> Optional[WizardState]:
        """Get current wizard state."""
        return self._state

    def get_available_templates(self) -> list[TemplateConfig]:
        """Get list of available export templates."""
        return list(TEMPLATE_CONFIGS.values())

    def get_template_config(self, template: ExportTemplate) -> Optional[TemplateConfig]:
        """Get configuration for a specific template."""
        return TEMPLATE_CONFIGS.get(template)

    # -------------------------------------------------------------------------
    # Step Navigation
    # -------------------------------------------------------------------------

    def next_step(self) -> WizardStep:
        """Move to the next wizard step."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        steps = list(WizardStep)
        current_idx = steps.index(self._state.current_step)

        if current_idx < len(steps) - 1:
            self._state.completed_steps.append(self._state.current_step)
            self._state.current_step = steps[current_idx + 1]
            self._state.modified_at = datetime.utcnow()

        return self._state.current_step

    def previous_step(self) -> WizardStep:
        """Move to the previous wizard step."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        steps = list(WizardStep)
        current_idx = steps.index(self._state.current_step)

        if current_idx > 0:
            self._state.current_step = steps[current_idx - 1]
            if self._state.current_step in self._state.completed_steps:
                self._state.completed_steps.remove(self._state.current_step)
            self._state.modified_at = datetime.utcnow()

        return self._state.current_step

    def go_to_step(self, step: WizardStep) -> WizardStep:
        """Jump to a specific wizard step."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        self._state.current_step = step
        self._state.modified_at = datetime.utcnow()
        return self._state.current_step

    # -------------------------------------------------------------------------
    # Configuration Updates
    # -------------------------------------------------------------------------

    def set_format(
        self,
        publication_format: PublicationFormat,
        export_format: ExportFormat,
    ) -> WizardState:
        """Set publication and export formats."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        self._state.publication_format = publication_format
        self._state.export_format = export_format
        self._state.modified_at = datetime.utcnow()
        return self._state

    def set_content_options(
        self,
        include_tables: bool = True,
        include_figures: bool = True,
        include_methodology: bool = True,
        include_citations: bool = True,
        include_results: bool = True,
    ) -> WizardState:
        """Set content inclusion options."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        self._state.include_tables = include_tables
        self._state.include_figures = include_figures
        self._state.include_methodology = include_methodology
        self._state.include_citations = include_citations
        self._state.include_results = include_results
        self._state.modified_at = datetime.utcnow()
        return self._state

    def set_style_options(
        self,
        table_style: Optional[TableStyle] = None,
        figure_style: Optional[FigureStyle] = None,
        figure_dpi: Optional[int] = None,
    ) -> WizardState:
        """Set style options."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        if table_style:
            self._state.table_style = table_style
        if figure_style:
            self._state.figure_style = figure_style
        if figure_dpi:
            self._state.figure_dpi = figure_dpi

        self._state.modified_at = datetime.utcnow()
        return self._state

    def set_metadata(
        self,
        title: Optional[str] = None,
        authors: Optional[list[str]] = None,
        abstract: Optional[str] = None,
        keywords: Optional[list[str]] = None,
    ) -> WizardState:
        """Set publication metadata."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        if title is not None:
            self._state.title = title
        if authors is not None:
            self._state.authors = authors
        if abstract is not None:
            self._state.abstract = abstract
        if keywords is not None:
            self._state.keywords = keywords

        self._state.modified_at = datetime.utcnow()
        return self._state

    def add_table(self, table: TableData) -> WizardState:
        """Add a table to the export."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        self._state.tables.append(table)
        self._state.modified_at = datetime.utcnow()
        return self._state

    def add_figure(self, figure: FigureData) -> WizardState:
        """Add a figure to the export."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        self._state.figures.append(figure)
        self._state.modified_at = datetime.utcnow()
        return self._state

    def set_methodology(self, methodology: MethodologySection) -> WizardState:
        """Set the methodology section."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        self._state.methodology = methodology
        self._state.modified_at = datetime.utcnow()
        return self._state

    def add_citation(self, citation: Citation) -> WizardState:
        """Add a citation."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        self._state.citations.append(citation)
        self._state.modified_at = datetime.utcnow()
        return self._state

    def set_results(self, results: dict[str, Any]) -> WizardState:
        """Set results data."""
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        self._state.results = results
        self._state.modified_at = datetime.utcnow()
        return self._state

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate(self) -> ValidationResult:
        """Validate the current wizard configuration."""
        if self._state is None:
            return ValidationResult(
                valid=False,
                errors=["Wizard not started"],
            )

        errors: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        # Check required fields
        if not self._state.publication_format:
            errors.append("Publication format not selected")

        if not self._state.export_format:
            errors.append("Export format not selected")

        # Check content
        has_content = (
            self._state.tables or
            self._state.figures or
            self._state.methodology or
            self._state.citations or
            self._state.results
        )

        if not has_content:
            warnings.append("No content added for export")

        # Check metadata
        if not self._state.title:
            warnings.append("No title specified")
            suggestions.append("Add a descriptive title for your publication")

        if not self._state.authors:
            warnings.append("No authors specified")

        # Format-specific checks
        if self._state.publication_format == PublicationFormat.IEEE:
            if self._state.table_style != TableStyle.IEEE_STANDARD:
                suggestions.append("Consider using IEEE_STANDARD table style for IEEE publications")

        if self._state.publication_format == PublicationFormat.ACM:
            if self._state.table_style != TableStyle.BOOKTABS:
                suggestions.append("Consider using BOOKTABS table style for ACM publications")

        # Figure DPI check
        if self._state.figure_dpi < 300:
            warnings.append(f"Figure DPI ({self._state.figure_dpi}) is below recommended 300 DPI")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    def export(self, package_name: Optional[str] = None) -> dict[str, Any]:
        """
        Execute the export based on wizard configuration.

        Args:
            package_name: Name for the export package

        Returns:
            Export result with file paths and metadata
        """
        if self._state is None:
            raise ValueError("Wizard not started. Call start_wizard() first.")

        validation = self.validate()
        if not validation.valid:
            raise ValueError(f"Configuration invalid: {', '.join(validation.errors)}")

        # Create exporter with configured settings
        config = ExportConfig(
            publication_format=self._state.publication_format or PublicationFormat.IEEE,
            default_export_format=self._state.export_format or ExportFormat.LATEX,
            table_style=self._state.table_style,
            figure_style=self._state.figure_style,
            figure_dpi=self._state.figure_dpi,
            output_directory=str(self.output_dir),
        )

        exporter = PublicationExporter(config)

        # Generate package name
        if not package_name:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            package_name = f"export_{timestamp}"

        # Export content
        results = exporter.export_publication_package(
            tables=self._state.tables if self._state.include_tables else [],
            figures=self._state.figures if self._state.include_figures else [],
            methodology=self._state.methodology if self._state.include_methodology else None,
            citations=self._state.citations if self._state.include_citations else [],
            results=self._state.results if self._state.include_results else None,
            package_name=package_name,
        )

        return {
            "success": True,
            "package_name": package_name,
            "output_directory": str(self.output_dir / package_name),
            "export_count": len(results),
            "exports": [
                {
                    "type": r.export_type,
                    "format": r.export_format.value if r.export_format else None,
                    "path": r.output_path,
                }
                for r in results
            ],
            "validation": validation.model_dump(),
        }


# =============================================================================
# Publication Preview
# =============================================================================


class PublicationPreview:
    """
    Publication preview generator.

    S15.12: Generates previews of publication exports for
    review before final export.
    """

    def __init__(self):
        """Initialize publication preview generator."""
        self._exporter = PublicationExporter()

    def generate_preview(
        self,
        state: WizardState,
        preview_format: PreviewFormat = PreviewFormat.HTML,
    ) -> PreviewResult:
        """
        Generate a preview of the publication.

        Args:
            state: Current wizard state
            preview_format: Output format for preview

        Returns:
            PreviewResult with rendered preview
        """
        warnings: list[str] = []
        recommendations: list[str] = []

        if preview_format == PreviewFormat.HTML:
            content = self._generate_html_preview(state, warnings, recommendations)
        elif preview_format == PreviewFormat.TEXT:
            content = self._generate_text_preview(state, warnings, recommendations)
        else:
            content = self._generate_json_preview(state)

        # Estimate statistics
        word_count = len(content.split())
        estimated_pages = max(1, word_count // 500)

        return PreviewResult(
            success=True,
            preview_format=preview_format,
            content=content,
            warnings=warnings,
            recommendations=recommendations,
            estimated_pages=estimated_pages,
            word_count=word_count,
        )

    def _generate_html_preview(
        self,
        state: WizardState,
        warnings: list[str],
        recommendations: list[str],
    ) -> str:
        """Generate HTML preview."""
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            f"<title>{state.title or 'Publication Preview'}</title>",
            "<style>",
            "body { font-family: 'Times New Roman', serif; max-width: 800px; margin: 0 auto; padding: 20px; }",
            "h1 { text-align: center; }",
            ".authors { text-align: center; margin-bottom: 20px; }",
            ".abstract { margin: 20px 0; padding: 10px; background: #f5f5f5; }",
            ".keywords { font-style: italic; }",
            "table { border-collapse: collapse; width: 100%; margin: 20px 0; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background: #f0f0f0; }",
            ".figure { margin: 20px 0; text-align: center; }",
            ".figure img { max-width: 100%; }",
            ".figcaption { font-style: italic; margin-top: 10px; }",
            ".section { margin: 30px 0; }",
            ".section h2 { border-bottom: 1px solid #ccc; padding-bottom: 5px; }",
            ".warning { color: #856404; background: #fff3cd; padding: 10px; margin: 10px 0; }",
            ".info { color: #0c5460; background: #d1ecf1; padding: 10px; margin: 10px 0; }",
            "</style>",
            "</head>",
            "<body>",
        ]

        # Title
        if state.title:
            html_parts.append(f"<h1>{state.title}</h1>")
        else:
            html_parts.append("<h1>[Untitled]</h1>")
            warnings.append("No title specified")

        # Authors
        if state.authors:
            html_parts.append(f"<div class='authors'>{', '.join(state.authors)}</div>")
        else:
            warnings.append("No authors specified")

        # Abstract
        if state.abstract:
            html_parts.append("<div class='abstract'>")
            html_parts.append(f"<strong>Abstract:</strong> {state.abstract}")
            html_parts.append("</div>")

        # Keywords
        if state.keywords:
            html_parts.append(f"<div class='keywords'><strong>Keywords:</strong> {', '.join(state.keywords)}</div>")

        # Configuration summary
        html_parts.append("<div class='section'>")
        html_parts.append("<h2>Export Configuration</h2>")
        html_parts.append("<ul>")
        html_parts.append(f"<li>Publication Format: {state.publication_format.value if state.publication_format else 'Not set'}</li>")
        html_parts.append(f"<li>Export Format: {state.export_format.value if state.export_format else 'Not set'}</li>")
        html_parts.append(f"<li>Table Style: {state.table_style.value}</li>")
        html_parts.append(f"<li>Figure Style: {state.figure_style.value}</li>")
        html_parts.append(f"<li>Figure DPI: {state.figure_dpi}</li>")
        html_parts.append("</ul>")
        html_parts.append("</div>")

        # Tables
        if state.include_tables and state.tables:
            html_parts.append("<div class='section'>")
            html_parts.append(f"<h2>Tables ({len(state.tables)})</h2>")
            for i, table in enumerate(state.tables):
                html_parts.append(self._render_table_html(table, i + 1))
            html_parts.append("</div>")
        elif state.include_tables and not state.tables:
            recommendations.append("Consider adding tables to present your data")

        # Figures
        if state.include_figures and state.figures:
            html_parts.append("<div class='section'>")
            html_parts.append(f"<h2>Figures ({len(state.figures)})</h2>")
            for i, figure in enumerate(state.figures):
                html_parts.append(self._render_figure_html(figure, i + 1))
            html_parts.append("</div>")
        elif state.include_figures and not state.figures:
            recommendations.append("Consider adding figures to visualize your results")

        # Methodology
        if state.include_methodology and state.methodology:
            html_parts.append("<div class='section'>")
            html_parts.append("<h2>Methodology</h2>")
            html_parts.append(self._render_methodology_html(state.methodology))
            html_parts.append("</div>")

        # Citations
        if state.include_citations and state.citations:
            html_parts.append("<div class='section'>")
            html_parts.append(f"<h2>References ({len(state.citations)})</h2>")
            html_parts.append("<ol>")
            for citation in state.citations:
                html_parts.append(f"<li>{citation.author}. \"{citation.title}\". {citation.year}.</li>")
            html_parts.append("</ol>")
            html_parts.append("</div>")

        # Results
        if state.include_results and state.results:
            html_parts.append("<div class='section'>")
            html_parts.append("<h2>Results Data</h2>")
            html_parts.append(f"<pre>{json.dumps(state.results, indent=2)}</pre>")
            html_parts.append("</div>")

        html_parts.extend(["</body>", "</html>"])

        return "\n".join(html_parts)

    def _render_table_html(self, table: TableData, number: int) -> str:
        """Render a table as HTML."""
        html = [f"<div class='table'><p><strong>Table {number}:</strong> {table.caption}</p>"]
        html.append("<table>")

        # Header
        html.append("<thead><tr>")
        for col in table.columns:
            html.append(f"<th>{col.header}</th>")
        html.append("</tr></thead>")

        # Body
        html.append("<tbody>")
        for row in table.rows:
            html.append("<tr>")
            for col in table.columns:
                value = row.get(col.name, "")
                if col.format_spec and isinstance(value, (int, float)):
                    value = f"{value:{col.format_spec}}"
                html.append(f"<td>{value}</td>")
            html.append("</tr>")
        html.append("</tbody>")

        html.append("</table></div>")
        return "\n".join(html)

    def _render_figure_html(self, figure: FigureData, number: int) -> str:
        """Render a figure placeholder as HTML."""
        return f"""
        <div class='figure'>
            <div style='border: 1px dashed #ccc; padding: 40px; background: #f9f9f9;'>
                [Figure {number}: {figure.title}]<br>
                <small>File: {figure.file_path}</small>
            </div>
            <p class='figcaption'><strong>Figure {number}:</strong> {figure.caption}</p>
        </div>
        """

    def _render_methodology_html(self, methodology: MethodologySection) -> str:
        """Render methodology section as HTML."""
        html = [f"<p><strong>Experiment:</strong> {methodology.experiment_name}</p>"]

        if methodology.experiment_description:
            html.append(f"<p>{methodology.experiment_description}</p>")

        if methodology.home_configuration:
            html.append("<p><strong>Home Configuration:</strong></p>")
            html.append(f"<pre>{json.dumps(methodology.home_configuration, indent=2)}</pre>")

        if methodology.simulation_parameters:
            html.append("<p><strong>Simulation Parameters:</strong></p>")
            html.append(f"<pre>{json.dumps(methodology.simulation_parameters, indent=2)}</pre>")

        if methodology.random_seeds:
            html.append("<p><strong>Random Seeds:</strong></p>")
            html.append(f"<pre>{json.dumps(methodology.random_seeds, indent=2)}</pre>")

        html.append(f"<p><em>Configuration Hash: {methodology.compute_hash()}</em></p>")

        return "\n".join(html)

    def _generate_text_preview(
        self,
        state: WizardState,
        warnings: list[str],
        recommendations: list[str],
    ) -> str:
        """Generate plain text preview."""
        lines = []

        # Title
        lines.append("=" * 60)
        lines.append(state.title or "[Untitled]")
        lines.append("=" * 60)
        lines.append("")

        # Authors
        if state.authors:
            lines.append(", ".join(state.authors))
            lines.append("")

        # Abstract
        if state.abstract:
            lines.append("ABSTRACT")
            lines.append("-" * 40)
            lines.append(state.abstract)
            lines.append("")

        # Configuration
        lines.append("EXPORT CONFIGURATION")
        lines.append("-" * 40)
        lines.append(f"Publication Format: {state.publication_format.value if state.publication_format else 'Not set'}")
        lines.append(f"Export Format: {state.export_format.value if state.export_format else 'Not set'}")
        lines.append(f"Table Style: {state.table_style.value}")
        lines.append(f"Figure DPI: {state.figure_dpi}")
        lines.append("")

        # Content summary
        lines.append("CONTENT SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Tables: {len(state.tables)}")
        lines.append(f"Figures: {len(state.figures)}")
        lines.append(f"Methodology: {'Yes' if state.methodology else 'No'}")
        lines.append(f"Citations: {len(state.citations)}")
        lines.append(f"Results: {'Yes' if state.results else 'No'}")

        return "\n".join(lines)

    def _generate_json_preview(self, state: WizardState) -> str:
        """Generate JSON preview."""
        return state.model_dump_json(indent=2)

    def generate_latex_snippet(self, state: WizardState) -> str:
        """
        Generate a LaTeX snippet preview.

        Args:
            state: Current wizard state

        Returns:
            LaTeX code snippet
        """
        lines = [
            "% S5-HES Publication Export Preview",
            "% Generated: " + datetime.utcnow().isoformat(),
            "",
            r"\documentclass{article}",
            "",
        ]

        # Package suggestions based on format
        if state.publication_format == PublicationFormat.IEEE:
            lines.append("% IEEE format packages")
            lines.append(r"\usepackage{IEEEtran}")
        elif state.publication_format == PublicationFormat.ACM:
            lines.append("% ACM format packages")
            lines.append(r"\usepackage{acmart}")

        lines.extend([
            r"\usepackage{graphicx}",
            r"\usepackage{booktabs}",
            "",
            r"\begin{document}",
            "",
        ])

        # Title
        if state.title:
            lines.append(r"\title{" + state.title + "}")

        # Authors
        if state.authors:
            lines.append(r"\author{" + " \\and ".join(state.authors) + "}")

        lines.extend([
            r"\maketitle",
            "",
        ])

        # Abstract
        if state.abstract:
            lines.extend([
                r"\begin{abstract}",
                state.abstract,
                r"\end{abstract}",
                "",
            ])

        lines.extend([
            "% Content would be inserted here",
            f"% Tables: {len(state.tables)}",
            f"% Figures: {len(state.figures)}",
            f"% Citations: {len(state.citations)}",
            "",
            r"\end{document}",
        ])

        return "\n".join(lines)


# =============================================================================
# Singleton Pattern
# =============================================================================


_wizard_instance: Optional[ExportWizard] = None
_preview_instance: Optional[PublicationPreview] = None


def get_export_wizard() -> ExportWizard:
    """Get singleton ExportWizard instance."""
    global _wizard_instance
    if _wizard_instance is None:
        _wizard_instance = ExportWizard()
    return _wizard_instance


def get_publication_preview() -> PublicationPreview:
    """Get singleton PublicationPreview instance."""
    global _preview_instance
    if _preview_instance is None:
        _preview_instance = PublicationPreview()
    return _preview_instance
