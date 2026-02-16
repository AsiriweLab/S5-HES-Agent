"""
Publication Export API - S15 Features

REST API endpoints for publication-ready exports including:
- S15.1: Publication exporters (IEEE, ACM formats)
- S15.5: Plot generation
- S15.7: Jupyter notebook integration
- S15.11-12: Export wizard and preview
"""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import tempfile
from pathlib import Path

from src.output.exporters import (
    # Publication Exporter
    PublicationExporter,
    ExportConfig,
    PublicationFormat,
    ExportFormat,
    TableStyle,
    FigureStyle,
    TableData,
    TableColumn,
    Citation,
    MethodologySection,
    FigureData,
    create_table_from_dict,
    get_publication_exporter,
    # Plot Generator
    PlotGenerator,
    PlotData,
    PlotFormat,
    PlotStyle,
    ColorScheme,
    is_plotting_available,
    get_missing_dependencies,
    # Jupyter Integration
    JupyterIntegration,
    get_jupyter_integration,
    # Export Wizard
    ExportWizard,
    PublicationPreview,
    ExportTemplate,
    WizardStep,
    PreviewFormat,
    get_export_wizard,
    get_publication_preview,
)


router = APIRouter(prefix="/api/exports", tags=["Publication Exports"])


# =============================================================================
# Request/Response Models
# =============================================================================


class TableColumnRequest(BaseModel):
    """Request model for table column."""
    name: str
    header: str
    format_spec: Optional[str] = None
    alignment: str = "left"


class TableRequest(BaseModel):
    """Request model for creating a table."""
    title: str
    caption: str
    label: str
    columns: list[TableColumnRequest]
    rows: list[dict[str, Any]]


class TableFromDictRequest(BaseModel):
    """Request model for creating table from dictionary."""
    data: dict[str, list[Any]]
    title: str
    caption: str
    label: str
    column_config: Optional[dict[str, dict[str, str]]] = None


class CitationRequest(BaseModel):
    """Request model for citation."""
    cite_key: str
    entry_type: str = "article"
    title: str
    author: str
    year: int
    journal: Optional[str] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None


class MethodologyRequest(BaseModel):
    """Request model for methodology section."""
    title: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    equipment: list[str] = Field(default_factory=list)
    procedure_steps: list[str] = Field(default_factory=list)


class FigureRequest(BaseModel):
    """Request model for figure."""
    path: str
    caption: str
    label: str
    width: Optional[str] = None


class PlotRequest(BaseModel):
    """Request model for creating plots."""
    plot_type: str  # line, bar, scatter, heatmap, box, histogram
    title: str
    xlabel: str = ""
    ylabel: str = ""
    x_data: Optional[list[Any]] = None
    y_data: Optional[list[Any]] = None
    labels: Optional[list[str]] = None
    matrix_data: Optional[list[list[float]]] = None
    row_labels: Optional[list[str]] = None
    col_labels: Optional[list[str]] = None
    format: str = "png"
    style_preset: Optional[str] = None  # ieee_single, ieee_double, acm, presentation


class WizardStartRequest(BaseModel):
    """Request model for starting export wizard."""
    template: Optional[str] = None  # ExportTemplate value


class WizardFormatRequest(BaseModel):
    """Request model for setting wizard format."""
    publication_format: str  # ieee, acm, generic
    export_format: str  # latex, markdown, html


class WizardContentRequest(BaseModel):
    """Request model for setting wizard content options."""
    include_tables: bool = True
    include_figures: bool = True
    include_methodology: bool = False
    include_citations: bool = False


class WizardMetadataRequest(BaseModel):
    """Request model for setting wizard metadata."""
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)


class PreviewRequest(BaseModel):
    """Request model for generating preview."""
    format: str = "html"  # html, text, json


class NotebookRequest(BaseModel):
    """Request model for generating notebooks."""
    experiment_id: str
    include_sections: Optional[list[str]] = None


class ComparisonNotebookRequest(BaseModel):
    """Request for comparison notebook."""
    experiment_ids: list[str]
    comparison_metrics: list[str] = Field(default_factory=list)


# =============================================================================
# Publication Export Endpoints
# =============================================================================


@router.get("/status")
async def get_export_status() -> dict[str, Any]:
    """Get status of export system including available features."""
    return {
        "publication_exporter": True,
        "plot_generator": is_plotting_available(),
        "missing_plot_dependencies": get_missing_dependencies(),
        "jupyter_integration": True,
        "export_wizard": True,
        "available_templates": [t.value for t in ExportTemplate],
        "available_formats": {
            "publication": [f.value for f in PublicationFormat],
            "export": [f.value for f in ExportFormat],
            "plot": [f.value for f in PlotFormat],
        },
    }


@router.post("/tables/create")
async def create_table(request: TableRequest) -> dict[str, Any]:
    """Create a table and export it."""
    exporter = get_publication_exporter()

    columns = [
        TableColumn(
            name=col.name,
            header=col.header,
            format_spec=col.format_spec,
            alignment=col.alignment,
        )
        for col in request.columns
    ]

    table = TableData(
        title=request.title,
        caption=request.caption,
        label=request.label,
        columns=columns,
        rows=request.rows,
    )

    # Export as LaTeX by default
    result = exporter.export_table(table, format="latex")

    return {
        "success": result.success,
        "output_path": result.output_path,
        "content": result.content,
        "format": result.format,
    }


@router.post("/tables/from-dict")
async def create_table_from_dictionary(request: TableFromDictRequest) -> dict[str, Any]:
    """Create a table from a dictionary of column data."""
    table = create_table_from_dict(
        data=request.data,
        title=request.title,
        caption=request.caption,
        label=request.label,
        column_config=request.column_config,
    )

    exporter = get_publication_exporter()
    result = exporter.export_table(table, format="latex")

    return {
        "success": result.success,
        "table_id": table.table_id,
        "output_path": result.output_path,
        "content": result.content,
    }


@router.post("/citations")
async def export_citations(citations: list[CitationRequest]) -> dict[str, Any]:
    """Export citations as BibTeX."""
    exporter = get_publication_exporter()

    citation_list = [
        Citation(
            cite_key=c.cite_key,
            entry_type=c.entry_type,
            title=c.title,
            author=c.author,
            year=c.year,
            journal=c.journal,
            volume=c.volume,
            pages=c.pages,
            doi=c.doi,
        )
        for c in citations
    ]

    result = exporter.export_citations(citation_list)

    return {
        "success": result.success,
        "output_path": result.output_path,
        "content": result.content,
        "citation_count": len(citation_list),
    }


@router.post("/methodology")
async def export_methodology(request: MethodologyRequest) -> dict[str, Any]:
    """Export methodology section."""
    exporter = get_publication_exporter()

    methodology = MethodologySection(
        title=request.title,
        description=request.description,
        parameters=request.parameters,
        equipment=request.equipment,
        procedure_steps=request.procedure_steps,
    )

    # Export as both LaTeX and Markdown
    latex_result = exporter.export_methodology(methodology, format="latex")
    md_result = exporter.export_methodology(methodology, format="markdown")

    return {
        "success": latex_result.success,
        "latex": {
            "content": latex_result.content,
            "output_path": latex_result.output_path,
        },
        "markdown": {
            "content": md_result.content,
            "output_path": md_result.output_path,
        },
    }


@router.get("/stats")
async def get_export_stats() -> dict[str, Any]:
    """Get export statistics."""
    exporter = get_publication_exporter()
    return exporter.get_stats()


@router.get("/history")
async def get_export_history(limit: int = Query(default=10, ge=1, le=100)) -> list[dict]:
    """Get export history."""
    exporter = get_publication_exporter()
    history = exporter.get_export_history()
    return [h.model_dump() for h in history[:limit]]


# =============================================================================
# Plot Generation Endpoints (S15.5)
# =============================================================================


@router.get("/plots/status")
async def get_plot_status() -> dict[str, Any]:
    """Check if plotting is available."""
    return {
        "available": is_plotting_available(),
        "missing_dependencies": get_missing_dependencies(),
        "supported_formats": [f.value for f in PlotFormat],
        "color_schemes": [c.value for c in ColorScheme],
    }


@router.post("/plots/create")
async def create_plot(request: PlotRequest) -> dict[str, Any]:
    """Create a publication-quality plot."""
    if not is_plotting_available():
        raise HTTPException(
            status_code=503,
            detail=f"Plotting not available. Missing: {get_missing_dependencies()}",
        )

    generator = PlotGenerator()

    # Apply style preset if specified
    if request.style_preset:
        presets = {
            "ieee_single": PlotStyle.ieee_single_column,
            "ieee_double": PlotStyle.ieee_double_column,
            "acm": PlotStyle.acm_single_column,
            "presentation": PlotStyle.presentation,
        }
        if request.style_preset in presets:
            generator.style = presets[request.style_preset]()

    # Parse format
    try:
        plot_format = PlotFormat(request.format)
    except ValueError:
        plot_format = PlotFormat.PNG

    # Create plot data
    data = PlotData(
        title=request.title,
        xlabel=request.xlabel,
        ylabel=request.ylabel,
        x_data=request.x_data,
        y_data=request.y_data,
        labels=request.labels,
        matrix_data=request.matrix_data,
        row_labels=request.row_labels,
        col_labels=request.col_labels,
    )

    # Create plot based on type
    plot_methods = {
        "line": generator.create_line_plot,
        "bar": generator.create_bar_plot,
        "scatter": generator.create_scatter_plot,
        "heatmap": generator.create_heatmap,
        "box": generator.create_box_plot,
        "histogram": generator.create_histogram,
        "confusion_matrix": generator.create_confusion_matrix,
    }

    if request.plot_type not in plot_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown plot type: {request.plot_type}. Available: {list(plot_methods.keys())}",
        )

    result = plot_methods[request.plot_type](data, plot_format)

    return {
        "success": result.success,
        "output_path": result.output_path,
        "format": result.format.value,
        "file_size_bytes": result.file_size_bytes,
        "base64_data": result.base64_data,
        "plot_id": data.plot_id,
    }


@router.get("/plots/history")
async def get_plot_history() -> list[dict]:
    """Get plot generation history."""
    generator = PlotGenerator()
    return [p.model_dump() for p in generator.get_plot_history()]


@router.get("/plots/stats")
async def get_plot_stats() -> dict[str, Any]:
    """Get plot generation statistics."""
    generator = PlotGenerator()
    return generator.get_stats()


# =============================================================================
# Jupyter Integration Endpoints (S15.7/S15.9)
# =============================================================================


@router.post("/jupyter/notebook")
async def generate_analysis_notebook(request: NotebookRequest) -> dict[str, Any]:
    """Generate an analysis Jupyter notebook."""
    jupyter = get_jupyter_integration()

    notebook_path = jupyter.generate_analysis_notebook(
        experiment_id=request.experiment_id,
        include_sections=request.include_sections,
    )

    return {
        "success": True,
        "notebook_path": notebook_path,
        "experiment_id": request.experiment_id,
    }


@router.post("/jupyter/comparison-notebook")
async def generate_comparison_notebook(request: ComparisonNotebookRequest) -> dict[str, Any]:
    """Generate a comparison Jupyter notebook."""
    jupyter = get_jupyter_integration()

    notebook_path = jupyter.generate_comparison_notebook(
        experiment_ids=request.experiment_ids,
        comparison_metrics=request.comparison_metrics,
    )

    return {
        "success": True,
        "notebook_path": notebook_path,
        "experiment_ids": request.experiment_ids,
    }


@router.get("/jupyter/snippet/{operation}")
async def get_code_snippet(
    operation: str,
    filepath: Optional[str] = None,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
) -> dict[str, str]:
    """Get a code snippet for Jupyter usage."""
    jupyter = get_jupyter_integration()

    kwargs = {}
    if filepath:
        kwargs["filepath"] = filepath
    if title:
        kwargs["title"] = title
    if xlabel:
        kwargs["xlabel"] = xlabel
    if ylabel:
        kwargs["ylabel"] = ylabel

    snippet = jupyter.get_code_snippet(operation, **kwargs)

    return {
        "operation": operation,
        "snippet": snippet,
    }


# =============================================================================
# Export Wizard Endpoints (S15.11-12)
# =============================================================================


@router.get("/wizard/templates")
async def get_available_templates() -> list[dict[str, Any]]:
    """Get available export templates."""
    wizard = get_export_wizard()
    templates = wizard.get_available_templates()
    return [
        {
            "template_id": t.template_id.value,
            "name": t.name,
            "description": t.description,
            "publication_format": t.publication_format.value,
            "export_format": t.export_format.value,
            "figure_dpi": t.figure_dpi,
            "column_count": t.column_count,
        }
        for t in templates
    ]


@router.post("/wizard/start")
async def start_wizard(request: WizardStartRequest) -> dict[str, Any]:
    """Start a new export wizard session."""
    wizard = get_export_wizard()

    template = None
    if request.template:
        try:
            template = ExportTemplate(request.template)
        except ValueError:
            pass

    state = wizard.start_wizard(template=template)

    return {
        "wizard_id": state.wizard_id,
        "current_step": state.current_step.value,
        "template": state.template.value if state.template else None,
        "publication_format": state.publication_format.value if state.publication_format else None,
    }


@router.get("/wizard/state")
async def get_wizard_state() -> dict[str, Any]:
    """Get current wizard state."""
    wizard = get_export_wizard()
    state = wizard.get_current_state()

    if not state:
        raise HTTPException(status_code=404, detail="No active wizard session")

    return {
        "wizard_id": state.wizard_id,
        "current_step": state.current_step.value,
        "template": state.template.value if state.template else None,
        "publication_format": state.publication_format.value if state.publication_format else None,
        "export_format": state.export_format.value if state.export_format else None,
        "title": state.title,
        "authors": state.authors,
        "include_tables": state.include_tables,
        "include_figures": state.include_figures,
        "include_methodology": state.include_methodology,
        "include_citations": state.include_citations,
        "table_count": len(state.tables),
        "figure_count": len(state.figures),
        "citation_count": len(state.citations),
    }


@router.post("/wizard/next")
async def wizard_next_step() -> dict[str, str]:
    """Move to next wizard step."""
    wizard = get_export_wizard()
    step = wizard.next_step()
    return {"current_step": step.value}


@router.post("/wizard/previous")
async def wizard_previous_step() -> dict[str, str]:
    """Move to previous wizard step."""
    wizard = get_export_wizard()
    step = wizard.previous_step()
    return {"current_step": step.value}


@router.post("/wizard/go-to/{step}")
async def wizard_go_to_step(step: str) -> dict[str, str]:
    """Jump to a specific wizard step."""
    wizard = get_export_wizard()
    try:
        target_step = WizardStep(step)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step: {step}. Available: {[s.value for s in WizardStep]}",
        )

    result = wizard.go_to_step(target_step)
    return {"current_step": result.value}


@router.post("/wizard/format")
async def set_wizard_format(request: WizardFormatRequest) -> dict[str, Any]:
    """Set publication and export format."""
    wizard = get_export_wizard()

    try:
        pub_format = PublicationFormat(request.publication_format)
        exp_format = ExportFormat(request.export_format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    state = wizard.set_format(pub_format, exp_format)

    return {
        "publication_format": state.publication_format.value,
        "export_format": state.export_format.value,
    }


@router.post("/wizard/content")
async def set_wizard_content(request: WizardContentRequest) -> dict[str, Any]:
    """Set content options."""
    wizard = get_export_wizard()

    state = wizard.set_content_options(
        include_tables=request.include_tables,
        include_figures=request.include_figures,
        include_methodology=request.include_methodology,
        include_citations=request.include_citations,
    )

    return {
        "include_tables": state.include_tables,
        "include_figures": state.include_figures,
        "include_methodology": state.include_methodology,
        "include_citations": state.include_citations,
    }


@router.post("/wizard/metadata")
async def set_wizard_metadata(request: WizardMetadataRequest) -> dict[str, Any]:
    """Set publication metadata."""
    wizard = get_export_wizard()

    state = wizard.set_metadata(
        title=request.title,
        authors=request.authors,
        abstract=request.abstract,
        keywords=request.keywords,
    )

    return {
        "title": state.title,
        "authors": state.authors,
        "abstract": state.abstract,
        "keywords": state.keywords,
    }


@router.post("/wizard/add-table")
async def add_wizard_table(request: TableRequest) -> dict[str, Any]:
    """Add a table to the wizard."""
    wizard = get_export_wizard()

    columns = [
        TableColumn(
            name=col.name,
            header=col.header,
            format_spec=col.format_spec,
            alignment=col.alignment,
        )
        for col in request.columns
    ]

    table = TableData(
        title=request.title,
        caption=request.caption,
        label=request.label,
        columns=columns,
        rows=request.rows,
    )

    state = wizard.add_table(table)

    return {
        "table_count": len(state.tables),
        "added_table_id": table.table_id,
    }


@router.post("/wizard/validate")
async def validate_wizard() -> dict[str, Any]:
    """Validate current wizard configuration."""
    wizard = get_export_wizard()
    result = wizard.validate()

    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
    }


@router.post("/wizard/preview")
async def generate_wizard_preview(request: PreviewRequest) -> dict[str, Any]:
    """Generate a preview of the export."""
    wizard = get_export_wizard()
    preview = get_publication_preview()

    state = wizard.get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active wizard session")

    try:
        preview_format = PreviewFormat(request.format)
    except ValueError:
        preview_format = PreviewFormat.HTML

    result = preview.generate_preview(state, preview_format)

    return {
        "success": result.success,
        "content": result.content,
        "format": result.format.value,
        "word_count": result.word_count,
        "table_count": result.table_count,
        "figure_count": result.figure_count,
    }


@router.post("/wizard/latex-snippet")
async def get_latex_snippet() -> dict[str, str]:
    """Get LaTeX snippet for current wizard state."""
    wizard = get_export_wizard()
    preview = get_publication_preview()

    state = wizard.get_current_state()
    if not state:
        raise HTTPException(status_code=404, detail="No active wizard session")

    latex = preview.generate_latex_snippet(state)

    return {"latex": latex}
