"""
Publication Exporter - Export infrastructure for academic publications.

S15.1: Provides publication-ready export capabilities for IEEE, ACM, and other
academic formats. Supports:
- LaTeX table generation from results
- IEEE-format figure export (vector graphics)
- BibTeX citation generation
- Publication-quality plots with customizable styling
- Experiment methodology auto-documentation
"""

import json
import csv
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Enumerations
# =============================================================================


class PublicationFormat(str, Enum):
    """Supported publication format standards."""
    IEEE = "ieee"
    ACM = "acm"
    SPRINGER = "springer"
    ELSEVIER = "elsevier"
    GENERIC = "generic"


class ExportFormat(str, Enum):
    """Output file formats."""
    LATEX = "latex"
    CSV = "csv"
    JSON = "json"
    BIBTEX = "bibtex"
    MARKDOWN = "markdown"
    SVG = "svg"
    PDF = "pdf"
    PNG = "png"


class TableStyle(str, Enum):
    """Table formatting styles."""
    IEEE_STANDARD = "ieee_standard"
    IEEE_DOUBLE_COLUMN = "ieee_double_column"
    ACM_STANDARD = "acm_standard"
    BOOKTABS = "booktabs"  # Professional LaTeX tables
    SIMPLE = "simple"


class FigureStyle(str, Enum):
    """Figure formatting styles."""
    IEEE_SINGLE_COLUMN = "ieee_single_column"
    IEEE_DOUBLE_COLUMN = "ieee_double_column"
    ACM_STANDARD = "acm_standard"
    PRESENTATION = "presentation"
    THESIS = "thesis"


# =============================================================================
# Data Models
# =============================================================================


class Citation(BaseModel):
    """BibTeX citation entry."""
    cite_key: str
    entry_type: str = "misc"  # article, inproceedings, misc, etc.
    title: str
    author: str
    year: int
    journal: Optional[str] = None
    booktitle: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    note: Optional[str] = None
    abstract: Optional[str] = None

    def to_bibtex(self) -> str:
        """Convert to BibTeX format."""
        lines = [f"@{self.entry_type}{{{self.cite_key},"]

        fields = [
            ("title", self.title),
            ("author", self.author),
            ("year", str(self.year)),
            ("journal", self.journal),
            ("booktitle", self.booktitle),
            ("volume", self.volume),
            ("number", self.number),
            ("pages", self.pages),
            ("publisher", self.publisher),
            ("doi", self.doi),
            ("url", self.url),
            ("note", self.note),
        ]

        for field_name, value in fields:
            if value:
                # Escape special LaTeX characters
                escaped_value = value.replace("&", r"\&").replace("%", r"\%")
                lines.append(f"  {field_name} = {{{escaped_value}}},")

        lines.append("}")
        return "\n".join(lines)


class TableColumn(BaseModel):
    """Definition of a table column."""
    name: str
    header: str
    alignment: str = "c"  # l, c, r
    format_spec: Optional[str] = None  # Python format spec for numbers
    width: Optional[str] = None  # LaTeX column width


class TableData(BaseModel):
    """Data for table export."""
    title: str
    caption: str
    label: str
    columns: list[TableColumn]
    rows: list[dict[str, Any]]
    notes: Optional[str] = None
    source: Optional[str] = None


class FigureData(BaseModel):
    """Data for figure export."""
    title: str
    caption: str
    label: str
    width: str = r"\columnwidth"
    height: Optional[str] = None
    file_path: str
    notes: Optional[str] = None


class MethodologySection(BaseModel):
    """Auto-generated methodology section."""
    section_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = "Methodology"

    # Experiment details
    experiment_name: str
    experiment_description: Optional[str] = None

    # Configuration
    home_configuration: dict[str, Any] = Field(default_factory=dict)
    simulation_parameters: dict[str, Any] = Field(default_factory=dict)
    threat_scenarios: list[dict[str, Any]] = Field(default_factory=list)

    # Reproducibility
    software_versions: dict[str, str] = Field(default_factory=dict)
    hardware_specs: dict[str, str] = Field(default_factory=dict)
    random_seeds: dict[str, int] = Field(default_factory=dict)

    # Provenance
    data_sources: list[str] = Field(default_factory=list)
    rag_sources_used: list[dict[str, Any]] = Field(default_factory=list)
    verification_status: str = "verified"

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def compute_hash(self) -> str:
        """Compute configuration hash for reproducibility."""
        content = json.dumps({
            "home": self.home_configuration,
            "simulation": self.simulation_parameters,
            "threats": self.threat_scenarios,
            "seeds": self.random_seeds,
        }, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:12]


class ExportResult(BaseModel):
    """Result of an export operation."""
    success: bool
    export_format: ExportFormat
    output_path: str
    file_size_bytes: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExportConfig(BaseModel):
    """Configuration for publication export."""
    publication_format: PublicationFormat = PublicationFormat.IEEE
    output_directory: str = "exports"
    include_timestamps: bool = True
    include_provenance: bool = True
    include_reproducibility_info: bool = True
    figure_dpi: int = 300
    figure_format: ExportFormat = ExportFormat.PDF
    table_style: TableStyle = TableStyle.IEEE_STANDARD
    figure_style: FigureStyle = FigureStyle.IEEE_SINGLE_COLUMN


# =============================================================================
# Format Generators (Abstract Base)
# =============================================================================


class FormatGenerator(ABC):
    """Abstract base class for format generators."""

    @abstractmethod
    def generate_table(self, data: TableData, style: TableStyle) -> str:
        """Generate a table in the specific format."""
        pass

    @abstractmethod
    def generate_methodology(self, methodology: MethodologySection) -> str:
        """Generate methodology section."""
        pass

    @abstractmethod
    def get_format_extension(self) -> str:
        """Get file extension for this format."""
        pass


class LaTeXGenerator(FormatGenerator):
    """LaTeX format generator."""

    def __init__(self, publication_format: PublicationFormat = PublicationFormat.IEEE):
        self.publication_format = publication_format

    def generate_table(self, data: TableData, style: TableStyle) -> str:
        """Generate LaTeX table."""
        lines = []

        # Begin table environment
        if style in [TableStyle.IEEE_STANDARD, TableStyle.IEEE_DOUBLE_COLUMN]:
            lines.append(r"\begin{table}[htbp]")
            if style == TableStyle.IEEE_DOUBLE_COLUMN:
                lines[-1] = r"\begin{table*}[htbp]"
        else:
            lines.append(r"\begin{table}[htbp]")

        lines.append(r"\centering")
        lines.append(f"\\caption{{{data.caption}}}")
        lines.append(f"\\label{{{data.label}}}")

        # Column specification
        col_spec = "|".join([col.alignment for col in data.columns])
        if style == TableStyle.BOOKTABS:
            col_spec = " ".join([col.alignment for col in data.columns])
            lines.append(f"\\begin{{tabular}}{{{col_spec}}}")
            lines.append(r"\toprule")
        else:
            lines.append(f"\\begin{{tabular}}{{|{col_spec}|}}")
            lines.append(r"\hline")

        # Header row
        headers = [col.header for col in data.columns]
        lines.append(" & ".join([f"\\textbf{{{h}}}" for h in headers]) + r" \\")

        if style == TableStyle.BOOKTABS:
            lines.append(r"\midrule")
        else:
            lines.append(r"\hline")

        # Data rows
        for row in data.rows:
            values = []
            for col in data.columns:
                value = row.get(col.name, "")
                if col.format_spec and isinstance(value, (int, float)):
                    value = format(value, col.format_spec)
                values.append(str(value))
            lines.append(" & ".join(values) + r" \\")

        # Close table
        if style == TableStyle.BOOKTABS:
            lines.append(r"\bottomrule")
        else:
            lines.append(r"\hline")

        lines.append(r"\end{tabular}")

        # Notes
        if data.notes:
            lines.append(f"\\\\[0.5em]")
            lines.append(f"\\footnotesize{{{data.notes}}}")

        # Close table environment
        if style == TableStyle.IEEE_DOUBLE_COLUMN:
            lines.append(r"\end{table*}")
        else:
            lines.append(r"\end{table}")

        return "\n".join(lines)

    def generate_figure(self, data: FigureData, style: FigureStyle) -> str:
        """Generate LaTeX figure inclusion."""
        lines = []

        # Determine environment
        if style == FigureStyle.IEEE_DOUBLE_COLUMN:
            lines.append(r"\begin{figure*}[htbp]")
        else:
            lines.append(r"\begin{figure}[htbp]")

        lines.append(r"\centering")

        # Include graphics
        options = [f"width={data.width}"]
        if data.height:
            options.append(f"height={data.height}")

        lines.append(f"\\includegraphics[{','.join(options)}]{{{data.file_path}}}")
        lines.append(f"\\caption{{{data.caption}}}")
        lines.append(f"\\label{{{data.label}}}")

        # Notes
        if data.notes:
            lines.append(f"\\\\[0.5em]")
            lines.append(f"\\footnotesize{{{data.notes}}}")

        # Close
        if style == FigureStyle.IEEE_DOUBLE_COLUMN:
            lines.append(r"\end{figure*}")
        else:
            lines.append(r"\end{figure}")

        return "\n".join(lines)

    def generate_methodology(self, methodology: MethodologySection) -> str:
        """Generate methodology section in LaTeX."""
        lines = []

        lines.append(f"\\section{{{methodology.title}}}")
        lines.append(f"\\label{{sec:methodology}}")
        lines.append("")

        # Experiment description
        if methodology.experiment_description:
            lines.append(f"\\subsection{{Experiment Overview}}")
            lines.append(methodology.experiment_description)
            lines.append("")

        # Configuration summary
        lines.append(f"\\subsection{{Simulation Configuration}}")
        lines.append("")

        # Home configuration
        if methodology.home_configuration:
            lines.append("\\subsubsection{Home Configuration}")
            lines.append("\\begin{itemize}")
            for key, value in methodology.home_configuration.items():
                lines.append(f"  \\item \\textbf{{{key}}}: {value}")
            lines.append("\\end{itemize}")
            lines.append("")

        # Simulation parameters
        if methodology.simulation_parameters:
            lines.append("\\subsubsection{Simulation Parameters}")
            lines.append("\\begin{itemize}")
            for key, value in methodology.simulation_parameters.items():
                lines.append(f"  \\item \\textbf{{{key}}}: {value}")
            lines.append("\\end{itemize}")
            lines.append("")

        # Threat scenarios
        if methodology.threat_scenarios:
            lines.append("\\subsubsection{Threat Scenarios}")
            lines.append(f"A total of {len(methodology.threat_scenarios)} threat scenarios were evaluated:")
            lines.append("\\begin{enumerate}")
            for scenario in methodology.threat_scenarios:
                name = scenario.get("name", "Unknown")
                threat_type = scenario.get("type", "N/A")
                lines.append(f"  \\item {name} ({threat_type})")
            lines.append("\\end{enumerate}")
            lines.append("")

        # Reproducibility section
        lines.append(f"\\subsection{{Reproducibility}}")
        lines.append("")

        # Configuration hash
        config_hash = methodology.compute_hash()
        lines.append(f"Configuration hash: \\texttt{{{config_hash}}}")
        lines.append("")

        # Software versions
        if methodology.software_versions:
            lines.append("\\subsubsection{Software Environment}")
            lines.append("\\begin{itemize}")
            for software, version in methodology.software_versions.items():
                lines.append(f"  \\item {software}: {version}")
            lines.append("\\end{itemize}")
            lines.append("")

        # Random seeds
        if methodology.random_seeds:
            lines.append("\\subsubsection{Random Seeds}")
            lines.append("The following random seeds were used to ensure reproducibility:")
            lines.append("\\begin{itemize}")
            for name, seed in methodology.random_seeds.items():
                lines.append(f"  \\item {name}: {seed}")
            lines.append("\\end{itemize}")
            lines.append("")

        # Data sources
        if methodology.data_sources:
            lines.append("\\subsubsection{Data Sources}")
            lines.append("\\begin{itemize}")
            for source in methodology.data_sources:
                lines.append(f"  \\item {source}")
            lines.append("\\end{itemize}")
            lines.append("")

        return "\n".join(lines)

    def get_format_extension(self) -> str:
        return ".tex"


class MarkdownGenerator(FormatGenerator):
    """Markdown format generator."""

    def generate_table(self, data: TableData, style: TableStyle) -> str:
        """Generate Markdown table."""
        lines = []

        # Title
        lines.append(f"### {data.title}")
        lines.append("")

        # Header row
        headers = [col.header for col in data.columns]
        lines.append("| " + " | ".join(headers) + " |")

        # Separator
        separators = []
        for col in data.columns:
            if col.alignment == "l":
                separators.append(":---")
            elif col.alignment == "r":
                separators.append("---:")
            else:
                separators.append(":---:")
        lines.append("| " + " | ".join(separators) + " |")

        # Data rows
        for row in data.rows:
            values = []
            for col in data.columns:
                value = row.get(col.name, "")
                if col.format_spec and isinstance(value, (int, float)):
                    value = format(value, col.format_spec)
                values.append(str(value))
            lines.append("| " + " | ".join(values) + " |")

        lines.append("")

        # Caption
        lines.append(f"*{data.caption}*")

        # Notes
        if data.notes:
            lines.append("")
            lines.append(f"**Note:** {data.notes}")

        return "\n".join(lines)

    def generate_methodology(self, methodology: MethodologySection) -> str:
        """Generate methodology section in Markdown."""
        lines = []

        lines.append(f"# {methodology.title}")
        lines.append("")

        if methodology.experiment_description:
            lines.append("## Experiment Overview")
            lines.append(methodology.experiment_description)
            lines.append("")

        lines.append("## Simulation Configuration")
        lines.append("")

        if methodology.home_configuration:
            lines.append("### Home Configuration")
            for key, value in methodology.home_configuration.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        if methodology.simulation_parameters:
            lines.append("### Simulation Parameters")
            for key, value in methodology.simulation_parameters.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        if methodology.threat_scenarios:
            lines.append("### Threat Scenarios")
            lines.append(f"A total of {len(methodology.threat_scenarios)} threat scenarios were evaluated:")
            for i, scenario in enumerate(methodology.threat_scenarios, 1):
                name = scenario.get("name", "Unknown")
                threat_type = scenario.get("type", "N/A")
                lines.append(f"{i}. {name} ({threat_type})")
            lines.append("")

        lines.append("## Reproducibility")
        lines.append("")
        lines.append(f"**Configuration hash:** `{methodology.compute_hash()}`")
        lines.append("")

        if methodology.software_versions:
            lines.append("### Software Environment")
            for software, version in methodology.software_versions.items():
                lines.append(f"- {software}: {version}")
            lines.append("")

        if methodology.random_seeds:
            lines.append("### Random Seeds")
            for name, seed in methodology.random_seeds.items():
                lines.append(f"- {name}: {seed}")
            lines.append("")

        return "\n".join(lines)

    def get_format_extension(self) -> str:
        return ".md"


# =============================================================================
# Publication Exporter Service
# =============================================================================


class PublicationExporter:
    """
    Main publication export service.

    Provides comprehensive export capabilities for academic publications:
    - LaTeX tables with IEEE/ACM formatting
    - BibTeX citations
    - Methodology auto-documentation
    - Publication-quality figure export
    - CSV/JSON data export
    """

    def __init__(self, config: Optional[ExportConfig] = None):
        """Initialize exporter with configuration."""
        self.config = config or ExportConfig()
        self.output_dir = Path(self.config.output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize generators
        self._latex_gen = LaTeXGenerator(self.config.publication_format)
        self._markdown_gen = MarkdownGenerator()

        # Export history
        self._exports: list[ExportResult] = []

    # -------------------------------------------------------------------------
    # Table Export
    # -------------------------------------------------------------------------

    def export_table(
        self,
        data: TableData,
        export_format: ExportFormat = ExportFormat.LATEX,
        style: Optional[TableStyle] = None,
        output_filename: Optional[str] = None,
    ) -> ExportResult:
        """
        Export a table in the specified format.

        Args:
            data: Table data to export
            export_format: Output format (LATEX, CSV, MARKDOWN)
            style: Table style to use
            output_filename: Custom output filename

        Returns:
            ExportResult with export details
        """
        style = style or self.config.table_style

        # Generate content
        if export_format == ExportFormat.LATEX:
            content = self._latex_gen.generate_table(data, style)
            ext = ".tex"
        elif export_format == ExportFormat.MARKDOWN:
            content = self._markdown_gen.generate_table(data, style)
            ext = ".md"
        elif export_format == ExportFormat.CSV:
            content = self._generate_csv_table(data)
            ext = ".csv"
        else:
            raise ValueError(f"Unsupported table format: {export_format}")

        # Determine output path
        filename = output_filename or f"table_{data.label}{ext}"
        output_path = self.output_dir / filename

        # Write file
        output_path.write_text(content, encoding="utf-8")

        result = ExportResult(
            success=True,
            export_format=export_format,
            output_path=str(output_path),
            file_size_bytes=output_path.stat().st_size,
            metadata={
                "table_label": data.label,
                "table_title": data.title,
                "row_count": len(data.rows),
                "column_count": len(data.columns),
            },
        )

        self._exports.append(result)
        return result

    def _generate_csv_table(self, data: TableData) -> str:
        """Generate CSV table content."""
        import io
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([col.header for col in data.columns])

        # Rows
        for row in data.rows:
            values = []
            for col in data.columns:
                value = row.get(col.name, "")
                if col.format_spec and isinstance(value, (int, float)):
                    value = format(value, col.format_spec)
                values.append(value)
            writer.writerow(values)

        return output.getvalue()

    # -------------------------------------------------------------------------
    # Figure Export
    # -------------------------------------------------------------------------

    def export_figure_latex(
        self,
        data: FigureData,
        style: Optional[FigureStyle] = None,
        output_filename: Optional[str] = None,
    ) -> ExportResult:
        """
        Export LaTeX figure inclusion code.

        Args:
            data: Figure data
            style: Figure style
            output_filename: Custom output filename

        Returns:
            ExportResult with export details
        """
        style = style or self.config.figure_style
        content = self._latex_gen.generate_figure(data, style)

        filename = output_filename or f"figure_{data.label}.tex"
        output_path = self.output_dir / filename
        output_path.write_text(content, encoding="utf-8")

        result = ExportResult(
            success=True,
            export_format=ExportFormat.LATEX,
            output_path=str(output_path),
            file_size_bytes=output_path.stat().st_size,
            metadata={
                "figure_label": data.label,
                "figure_title": data.title,
                "source_file": data.file_path,
            },
        )

        self._exports.append(result)
        return result

    # -------------------------------------------------------------------------
    # Citation Export
    # -------------------------------------------------------------------------

    def export_citations(
        self,
        citations: list[Citation],
        output_filename: Optional[str] = None,
    ) -> ExportResult:
        """
        Export citations in BibTeX format.

        Args:
            citations: List of citations to export
            output_filename: Custom output filename

        Returns:
            ExportResult with export details
        """
        content = "\n\n".join([c.to_bibtex() for c in citations])

        filename = output_filename or "references.bib"
        output_path = self.output_dir / filename
        output_path.write_text(content, encoding="utf-8")

        result = ExportResult(
            success=True,
            export_format=ExportFormat.BIBTEX,
            output_path=str(output_path),
            file_size_bytes=output_path.stat().st_size,
            metadata={
                "citation_count": len(citations),
                "cite_keys": [c.cite_key for c in citations],
            },
        )

        self._exports.append(result)
        return result

    def generate_self_citation(self) -> Citation:
        """Generate BibTeX citation for S5-HES Agent itself."""
        return Citation(
            cite_key="s5hes2024",
            entry_type="software",
            title="S5-HES Agent: Society 5.0 Smart Home Environment Simulator",
            author="S5-HES Development Team",
            year=datetime.now().year,
            url="https://github.com/s5hes/smart-home-simulator",
            note="An agentic RAG-enhanced IoT simulation framework for smart home security research",
        )

    # -------------------------------------------------------------------------
    # Methodology Export
    # -------------------------------------------------------------------------

    def export_methodology(
        self,
        methodology: MethodologySection,
        export_format: ExportFormat = ExportFormat.LATEX,
        output_filename: Optional[str] = None,
    ) -> ExportResult:
        """
        Export auto-generated methodology section.

        Args:
            methodology: Methodology data
            export_format: Output format (LATEX or MARKDOWN)
            output_filename: Custom output filename

        Returns:
            ExportResult with export details
        """
        if export_format == ExportFormat.LATEX:
            content = self._latex_gen.generate_methodology(methodology)
            ext = ".tex"
        elif export_format == ExportFormat.MARKDOWN:
            content = self._markdown_gen.generate_methodology(methodology)
            ext = ".md"
        else:
            raise ValueError(f"Unsupported methodology format: {export_format}")

        filename = output_filename or f"methodology{ext}"
        output_path = self.output_dir / filename
        output_path.write_text(content, encoding="utf-8")

        result = ExportResult(
            success=True,
            export_format=export_format,
            output_path=str(output_path),
            file_size_bytes=output_path.stat().st_size,
            metadata={
                "config_hash": methodology.compute_hash(),
                "experiment_name": methodology.experiment_name,
                "threat_count": len(methodology.threat_scenarios),
            },
        )

        self._exports.append(result)
        return result

    # -------------------------------------------------------------------------
    # Data Export
    # -------------------------------------------------------------------------

    def export_results_json(
        self,
        results: dict[str, Any],
        output_filename: Optional[str] = None,
        include_metadata: bool = True,
    ) -> ExportResult:
        """
        Export results as JSON.

        Args:
            results: Results data to export
            output_filename: Custom output filename
            include_metadata: Include export metadata

        Returns:
            ExportResult with export details
        """
        export_data = results.copy()

        if include_metadata:
            export_data["_export_metadata"] = {
                "exported_at": datetime.utcnow().isoformat(),
                "exporter_version": "1.0.0",
                "publication_format": self.config.publication_format.value,
            }

        filename = output_filename or "results.json"
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)

        result = ExportResult(
            success=True,
            export_format=ExportFormat.JSON,
            output_path=str(output_path),
            file_size_bytes=output_path.stat().st_size,
        )

        self._exports.append(result)
        return result

    # -------------------------------------------------------------------------
    # Batch Export
    # -------------------------------------------------------------------------

    def export_publication_package(
        self,
        tables: Optional[list[TableData]] = None,
        figures: Optional[list[FigureData]] = None,
        methodology: Optional[MethodologySection] = None,
        citations: Optional[list[Citation]] = None,
        results: Optional[dict[str, Any]] = None,
        package_name: str = "publication_export",
    ) -> list[ExportResult]:
        """
        Export a complete publication package.

        Creates a directory with all publication-ready materials.

        Args:
            tables: Tables to export
            figures: Figures to export
            methodology: Methodology section
            citations: Citations to export
            results: Results data
            package_name: Name for the export package

        Returns:
            List of ExportResult for all exported files
        """
        # Create package directory
        package_dir = self.output_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # Temporarily change output directory
        original_output_dir = self.output_dir
        self.output_dir = package_dir

        results_list = []

        try:
            # Export tables
            if tables:
                tables_dir = package_dir / "tables"
                tables_dir.mkdir(exist_ok=True)
                self.output_dir = tables_dir
                for table in tables:
                    results_list.append(self.export_table(table))

            # Export figures
            if figures:
                figures_dir = package_dir / "figures"
                figures_dir.mkdir(exist_ok=True)
                self.output_dir = figures_dir
                for figure in figures:
                    results_list.append(self.export_figure_latex(figure))

            # Export methodology
            if methodology:
                self.output_dir = package_dir
                results_list.append(self.export_methodology(methodology))

            # Export citations
            if citations:
                self.output_dir = package_dir
                # Always include self-citation
                all_citations = citations + [self.generate_self_citation()]
                results_list.append(self.export_citations(all_citations))

            # Export results
            if results:
                data_dir = package_dir / "data"
                data_dir.mkdir(exist_ok=True)
                self.output_dir = data_dir
                results_list.append(self.export_results_json(results))

            # Create manifest
            self.output_dir = package_dir
            manifest = {
                "package_name": package_name,
                "created_at": datetime.utcnow().isoformat(),
                "publication_format": self.config.publication_format.value,
                "contents": {
                    "tables": len(tables) if tables else 0,
                    "figures": len(figures) if figures else 0,
                    "methodology": bool(methodology),
                    "citations": len(citations) if citations else 0,
                    "results": bool(results),
                },
                "exports": [r.model_dump() for r in results_list],
            }

            manifest_path = package_dir / "manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2, default=str)

        finally:
            # Restore original output directory
            self.output_dir = original_output_dir

        return results_list

    # -------------------------------------------------------------------------
    # Statistics and History
    # -------------------------------------------------------------------------

    def get_export_history(self) -> list[ExportResult]:
        """Get history of all exports."""
        return self._exports.copy()

    def get_export_stats(self) -> dict[str, Any]:
        """Get export statistics."""
        total_size = sum(e.file_size_bytes for e in self._exports)
        format_counts = {}
        for export in self._exports:
            fmt = export.export_format.value
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

        return {
            "total_exports": len(self._exports),
            "total_size_bytes": total_size,
            "format_breakdown": format_counts,
            "output_directory": str(self.output_dir),
        }

    def clear_history(self) -> None:
        """Clear export history."""
        self._exports.clear()


# =============================================================================
# Convenience Functions
# =============================================================================


def create_table_from_dict(
    data: list[dict[str, Any]],
    title: str,
    caption: str,
    label: str,
    column_config: Optional[dict[str, dict[str, Any]]] = None,
) -> TableData:
    """
    Convenience function to create TableData from a list of dictionaries.

    Args:
        data: List of row dictionaries
        title: Table title
        caption: Table caption
        label: LaTeX label
        column_config: Optional column configuration {name: {header, alignment, format_spec}}

    Returns:
        TableData ready for export
    """
    if not data:
        return TableData(title=title, caption=caption, label=label, columns=[], rows=[])

    # Infer columns from first row
    column_config = column_config or {}
    columns = []

    for key in data[0].keys():
        config = column_config.get(key, {})
        columns.append(TableColumn(
            name=key,
            header=config.get("header", key.replace("_", " ").title()),
            alignment=config.get("alignment", "c"),
            format_spec=config.get("format_spec"),
        ))

    return TableData(
        title=title,
        caption=caption,
        label=label,
        columns=columns,
        rows=data,
    )


def create_methodology_from_experiment(
    experiment_name: str,
    home_config: dict[str, Any],
    simulation_params: dict[str, Any],
    threat_scenarios: list[dict[str, Any]],
    random_seed: int = 42,
    description: Optional[str] = None,
) -> MethodologySection:
    """
    Convenience function to create MethodologySection from experiment data.

    Args:
        experiment_name: Name of the experiment
        home_config: Home configuration dictionary
        simulation_params: Simulation parameters
        threat_scenarios: List of threat scenarios
        random_seed: Main random seed
        description: Optional experiment description

    Returns:
        MethodologySection ready for export
    """
    import platform
    import sys

    return MethodologySection(
        experiment_name=experiment_name,
        experiment_description=description,
        home_configuration=home_config,
        simulation_parameters=simulation_params,
        threat_scenarios=threat_scenarios,
        software_versions={
            "Python": sys.version.split()[0],
            "Platform": platform.platform(),
            "S5-HES Agent": "1.0.0",
        },
        random_seeds={
            "main_seed": random_seed,
            "numpy_seed": random_seed,
            "torch_seed": random_seed,
        },
    )


# =============================================================================
# Singleton Instance
# =============================================================================

_exporter_instance: Optional[PublicationExporter] = None


def get_publication_exporter(config: Optional[ExportConfig] = None) -> PublicationExporter:
    """Get or create the publication exporter singleton."""
    global _exporter_instance

    if _exporter_instance is None:
        _exporter_instance = PublicationExporter(config)

    return _exporter_instance


def initialize_publication_exporter(config: ExportConfig) -> PublicationExporter:
    """Initialize the publication exporter with custom config."""
    global _exporter_instance
    _exporter_instance = PublicationExporter(config)
    return _exporter_instance
