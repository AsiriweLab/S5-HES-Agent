"""
Jupyter Integration Module (S15.7).

Provides seamless integration with Jupyter notebooks for interactive
data analysis and visualization of S5-HES simulation results.

Features:
- Direct data access API for notebooks
- Interactive visualization widgets
- Export helpers for analysis results
- Notebook cell generators
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Enumerations
# =============================================================================


class OutputFormat(str, Enum):
    """Output format for display."""
    HTML = "html"
    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"


class WidgetType(str, Enum):
    """Interactive widget types."""
    DROPDOWN = "dropdown"
    SLIDER = "slider"
    CHECKBOX = "checkbox"
    TEXT_INPUT = "text_input"
    DATE_PICKER = "date_picker"
    MULTI_SELECT = "multi_select"


# =============================================================================
# Data Models
# =============================================================================


class DataAccessResult(BaseModel):
    """Result from data access operations."""
    success: bool
    data: Optional[Union[dict[str, Any], list[Any]]] = None
    dataframe_json: Optional[str] = None  # For pandas conversion
    row_count: int = 0
    column_count: int = 0
    columns: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class VisualizationConfig(BaseModel):
    """Configuration for visualizations."""
    viz_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    plot_type: str = "line"
    x_column: Optional[str] = None
    y_columns: list[str] = Field(default_factory=list)
    color_by: Optional[str] = None
    width: int = 800
    height: int = 400
    interactive: bool = True


class NotebookCell(BaseModel):
    """Represents a notebook cell."""
    cell_type: str = "code"  # code, markdown, raw
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotebookTemplate(BaseModel):
    """Template for generating notebooks."""
    template_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    cells: list[NotebookCell] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Jupyter Integration Class
# =============================================================================


class JupyterIntegration:
    """
    Jupyter notebook integration for S5-HES.

    S15.7: Provides interactive data analysis capabilities
    within Jupyter notebooks.
    """

    def __init__(
        self,
        api_base_url: str = "http://localhost:8000/api",
        output_dir: Optional[str] = None,
    ):
        """
        Initialize Jupyter integration.

        Args:
            api_base_url: Base URL for S5-HES API
            output_dir: Directory for saving outputs
        """
        self.api_base_url = api_base_url
        self.output_dir = Path(output_dir or "jupyter_outputs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Session data
        self._session_id: Optional[str] = None
        self._cached_data: dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # Data Access API (S15.9)
    # -------------------------------------------------------------------------

    def load_simulation_results(
        self,
        experiment_id: Optional[str] = None,
        filepath: Optional[str] = None,
    ) -> DataAccessResult:
        """
        Load simulation results for analysis.

        Args:
            experiment_id: ID of experiment to load
            filepath: Direct path to results file

        Returns:
            DataAccessResult with loaded data
        """
        try:
            if filepath:
                path = Path(filepath)
                if not path.exists():
                    return DataAccessResult(
                        success=False,
                        error=f"File not found: {filepath}"
                    )

                if path.suffix == ".json":
                    with open(path, 'r') as f:
                        data = json.load(f)
                elif path.suffix == ".csv":
                    # Return raw CSV content for pandas processing
                    content = path.read_text()
                    return DataAccessResult(
                        success=True,
                        data={"csv_content": content},
                        metadata={"format": "csv", "filepath": str(path)}
                    )
                else:
                    return DataAccessResult(
                        success=False,
                        error=f"Unsupported file format: {path.suffix}"
                    )

                # Process JSON data
                columns = []
                rows = []

                if isinstance(data, list) and data:
                    if isinstance(data[0], dict):
                        columns = list(data[0].keys())
                        rows = data
                elif isinstance(data, dict):
                    if "data" in data:
                        inner = data["data"]
                        if isinstance(inner, list) and inner:
                            columns = list(inner[0].keys()) if isinstance(inner[0], dict) else []
                            rows = inner
                    else:
                        columns = list(data.keys())
                        rows = [data]

                return DataAccessResult(
                    success=True,
                    data=data,
                    dataframe_json=json.dumps(rows),
                    row_count=len(rows),
                    column_count=len(columns),
                    columns=columns,
                    metadata={
                        "source": str(path),
                        "loaded_at": datetime.utcnow().isoformat(),
                    }
                )

            elif experiment_id:
                # Load from experiment ID (mock implementation)
                return DataAccessResult(
                    success=True,
                    data={"experiment_id": experiment_id, "status": "mock"},
                    metadata={"source": "api", "experiment_id": experiment_id}
                )

            else:
                return DataAccessResult(
                    success=False,
                    error="Either filepath or experiment_id must be provided"
                )

        except Exception as e:
            return DataAccessResult(success=False, error=str(e))

    def get_device_data(
        self,
        home_id: str,
        device_type: Optional[str] = None,
        time_range: Optional[tuple[datetime, datetime]] = None,
    ) -> DataAccessResult:
        """
        Get device telemetry data for analysis.

        Args:
            home_id: ID of the smart home
            device_type: Filter by device type
            time_range: Time range filter

        Returns:
            DataAccessResult with device data
        """
        # This would connect to the simulation API
        data = {
            "home_id": home_id,
            "device_type": device_type,
            "time_range": [t.isoformat() if t else None for t in (time_range or (None, None))],
            "devices": [],  # Would be populated from API
        }

        return DataAccessResult(
            success=True,
            data=data,
            metadata={"source": "device_api", "home_id": home_id}
        )

    def get_threat_events(
        self,
        simulation_id: str,
        threat_type: Optional[str] = None,
        include_labels: bool = True,
    ) -> DataAccessResult:
        """
        Get threat events with ground truth labels.

        Args:
            simulation_id: ID of simulation run
            threat_type: Filter by threat type
            include_labels: Include ground truth labels

        Returns:
            DataAccessResult with threat data
        """
        data = {
            "simulation_id": simulation_id,
            "threat_type": threat_type,
            "include_labels": include_labels,
            "events": [],  # Would be populated from API
        }

        return DataAccessResult(
            success=True,
            data=data,
            metadata={
                "source": "threat_api",
                "simulation_id": simulation_id,
                "has_ground_truth": include_labels,
            }
        )

    def get_network_traffic(
        self,
        simulation_id: str,
        protocol: Optional[str] = None,
    ) -> DataAccessResult:
        """
        Get network traffic data from simulation.

        Args:
            simulation_id: ID of simulation run
            protocol: Filter by protocol (mqtt, coap, http, websocket)

        Returns:
            DataAccessResult with network data
        """
        data = {
            "simulation_id": simulation_id,
            "protocol": protocol,
            "packets": [],  # Would be populated from API
        }

        return DataAccessResult(
            success=True,
            data=data,
            metadata={"source": "network_api", "protocol": protocol}
        )

    # -------------------------------------------------------------------------
    # Notebook Generation
    # -------------------------------------------------------------------------

    def generate_analysis_notebook(
        self,
        experiment_id: str,
        include_sections: Optional[list[str]] = None,
    ) -> str:
        """
        Generate a Jupyter notebook for experiment analysis.

        Args:
            experiment_id: Experiment to analyze
            include_sections: Sections to include

        Returns:
            Path to generated notebook
        """
        sections = include_sections or [
            "setup",
            "data_loading",
            "exploration",
            "visualization",
            "statistical_analysis",
        ]

        cells = []

        # Title cell
        cells.append(NotebookCell(
            cell_type="markdown",
            source=f"# S5-HES Experiment Analysis\n\n**Experiment ID:** `{experiment_id}`\n\n**Generated:** {datetime.utcnow().isoformat()}"
        ))

        if "setup" in sections:
            cells.append(NotebookCell(
                cell_type="markdown",
                source="## 1. Setup\n\nImport required libraries and initialize the S5-HES integration."
            ))
            cells.append(NotebookCell(
                cell_type="code",
                source="""# Import libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# S5-HES Integration
from src.output.exporters import JupyterIntegration

# Initialize
s5hes = JupyterIntegration()
print("S5-HES Jupyter Integration initialized")"""
            ))

        if "data_loading" in sections:
            cells.append(NotebookCell(
                cell_type="markdown",
                source="## 2. Data Loading\n\nLoad simulation results and prepare for analysis."
            ))
            cells.append(NotebookCell(
                cell_type="code",
                source=f"""# Load experiment data
result = s5hes.load_simulation_results(experiment_id="{experiment_id}")

if result.success:
    data = result.data
    print(f"Loaded {{result.row_count}} rows, {{result.column_count}} columns")
    print(f"Columns: {{result.columns}}")
else:
    print(f"Error: {{result.error}}")"""
            ))

        if "exploration" in sections:
            cells.append(NotebookCell(
                cell_type="markdown",
                source="## 3. Data Exploration\n\nExplore the dataset structure and statistics."
            ))
            cells.append(NotebookCell(
                cell_type="code",
                source="""# Convert to DataFrame if available
if result.dataframe_json:
    import json
    df = pd.DataFrame(json.loads(result.dataframe_json))
    display(df.head())
    display(df.describe())"""
            ))

        if "visualization" in sections:
            cells.append(NotebookCell(
                cell_type="markdown",
                source="## 4. Visualization\n\nCreate visualizations of the simulation results."
            ))
            cells.append(NotebookCell(
                cell_type="code",
                source="""# Set style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# Example: Timeline plot
fig, ax = plt.subplots(figsize=(12, 4))
# Add your visualization code here
plt.title("Simulation Timeline")
plt.tight_layout()
plt.show()"""
            ))

        if "statistical_analysis" in sections:
            cells.append(NotebookCell(
                cell_type="markdown",
                source="## 5. Statistical Analysis\n\nPerform statistical tests on the results."
            ))
            cells.append(NotebookCell(
                cell_type="code",
                source="""# Example statistical analysis
from scipy import stats

# Add your statistical analysis code here
# Example: t-test, chi-squared, etc.
print("Statistical analysis section - customize as needed")"""
            ))

        # Export section
        cells.append(NotebookCell(
            cell_type="markdown",
            source="## 6. Export Results\n\nExport analysis results for publication."
        ))
        cells.append(NotebookCell(
            cell_type="code",
            source="""# Export results
from src.output.exporters import PublicationExporter

exporter = PublicationExporter()

# Example: Export table
# result = exporter.export_table(table_data, 'latex')

print("Export section - customize as needed")"""
        ))

        # Create notebook structure
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {
                    "name": "python",
                    "version": "3.11.0"
                },
                "s5hes": {
                    "experiment_id": experiment_id,
                    "generated_at": datetime.utcnow().isoformat(),
                }
            },
            "cells": [
                {
                    "cell_type": cell.cell_type,
                    "metadata": cell.metadata,
                    "source": cell.source.split("\n"),
                    **({"outputs": [], "execution_count": None} if cell.cell_type == "code" else {})
                }
                for cell in cells
            ]
        }

        # Save notebook
        output_path = self.output_dir / f"analysis_{experiment_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.ipynb"
        with open(output_path, 'w') as f:
            json.dump(notebook, f, indent=2)

        return str(output_path)

    def generate_comparison_notebook(
        self,
        experiment_ids: list[str],
        comparison_metrics: Optional[list[str]] = None,
    ) -> str:
        """
        Generate a notebook comparing multiple experiments.

        Args:
            experiment_ids: List of experiments to compare
            comparison_metrics: Metrics to compare

        Returns:
            Path to generated notebook
        """
        metrics = comparison_metrics or ["accuracy", "precision", "recall", "f1_score"]

        cells = [
            NotebookCell(
                cell_type="markdown",
                source=f"# S5-HES Experiment Comparison\n\n**Experiments:** {', '.join(experiment_ids)}\n\n**Metrics:** {', '.join(metrics)}"
            ),
            NotebookCell(
                cell_type="code",
                source=f"""# Load all experiments
from src.output.exporters import JupyterIntegration
s5hes = JupyterIntegration()

experiment_ids = {experiment_ids}
results = {{}}

for exp_id in experiment_ids:
    results[exp_id] = s5hes.load_simulation_results(experiment_id=exp_id)
    print(f"Loaded: {{exp_id}}")"""
            ),
            NotebookCell(
                cell_type="code",
                source=f"""# Compare metrics
import pandas as pd
import matplotlib.pyplot as plt

metrics = {metrics}
# Add comparison visualization code here"""
            ),
        ]

        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
            },
            "cells": [
                {
                    "cell_type": cell.cell_type,
                    "metadata": cell.metadata,
                    "source": cell.source.split("\n"),
                    **({"outputs": [], "execution_count": None} if cell.cell_type == "code" else {})
                }
                for cell in cells
            ]
        }

        output_path = self.output_dir / f"comparison_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.ipynb"
        with open(output_path, 'w') as f:
            json.dump(notebook, f, indent=2)

        return str(output_path)

    # -------------------------------------------------------------------------
    # Display Helpers
    # -------------------------------------------------------------------------

    def display_dataframe(
        self,
        data: Union[list[dict], dict],
        title: Optional[str] = None,
        max_rows: int = 20,
    ) -> str:
        """
        Format data for display in Jupyter.

        Args:
            data: Data to display
            title: Optional title
            max_rows: Maximum rows to show

        Returns:
            HTML string for display
        """
        if isinstance(data, dict):
            if "data" in data:
                rows = data["data"][:max_rows]
            else:
                rows = [data]
        else:
            rows = data[:max_rows]

        if not rows:
            return "<p>No data to display</p>"

        # Build HTML table
        html_parts = []

        if title:
            html_parts.append(f"<h3>{title}</h3>")

        html_parts.append("<table border='1' class='dataframe'>")

        # Header
        if rows and isinstance(rows[0], dict):
            headers = list(rows[0].keys())
            html_parts.append("<thead><tr>")
            for h in headers:
                html_parts.append(f"<th>{h}</th>")
            html_parts.append("</tr></thead>")

            # Body
            html_parts.append("<tbody>")
            for row in rows:
                html_parts.append("<tr>")
                for h in headers:
                    html_parts.append(f"<td>{row.get(h, '')}</td>")
                html_parts.append("</tr>")
            html_parts.append("</tbody>")

        html_parts.append("</table>")

        if len(data) > max_rows:
            html_parts.append(f"<p><i>Showing {max_rows} of {len(data)} rows</i></p>")

        return "".join(html_parts)

    def display_summary_stats(
        self,
        data: list[dict],
        numeric_columns: Optional[list[str]] = None,
    ) -> str:
        """
        Display summary statistics.

        Args:
            data: Data to summarize
            numeric_columns: Columns to compute stats for

        Returns:
            HTML string with statistics
        """
        if not data:
            return "<p>No data for summary</p>"

        # Detect numeric columns
        if numeric_columns is None:
            first_row = data[0]
            numeric_columns = [
                k for k, v in first_row.items()
                if isinstance(v, (int, float))
            ]

        if not numeric_columns:
            return "<p>No numeric columns found</p>"

        # Compute stats
        stats = {}
        for col in numeric_columns:
            values = [row.get(col) for row in data if isinstance(row.get(col), (int, float))]
            if values:
                stats[col] = {
                    "count": len(values),
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "std": (sum((x - sum(values)/len(values))**2 for x in values) / len(values)) ** 0.5,
                }

        # Format as HTML
        html_parts = ["<table border='1' class='dataframe'>"]
        html_parts.append("<thead><tr><th>Statistic</th>")
        for col in numeric_columns:
            html_parts.append(f"<th>{col}</th>")
        html_parts.append("</tr></thead>")

        html_parts.append("<tbody>")
        for stat_name in ["count", "mean", "min", "max", "std"]:
            html_parts.append(f"<tr><th>{stat_name}</th>")
            for col in numeric_columns:
                value = stats.get(col, {}).get(stat_name, "N/A")
                if isinstance(value, float):
                    value = f"{value:.4f}"
                html_parts.append(f"<td>{value}</td>")
            html_parts.append("</tr>")
        html_parts.append("</tbody></table>")

        return "".join(html_parts)

    # -------------------------------------------------------------------------
    # Code Snippets
    # -------------------------------------------------------------------------

    def get_code_snippet(
        self,
        operation: str,
        **kwargs: Any,
    ) -> str:
        """
        Get a code snippet for common operations.

        Args:
            operation: Operation type
            **kwargs: Operation-specific parameters

        Returns:
            Python code snippet
        """
        snippets = {
            "load_data": """# Load simulation data
from src.output.exporters import JupyterIntegration

s5hes = JupyterIntegration()
result = s5hes.load_simulation_results(filepath="{filepath}")

if result.success:
    print(f"Loaded {{result.row_count}} rows")
""",

            "create_plot": """# Create visualization
from src.output.exporters import PlotGenerator, PlotData, PlotFormat

generator = PlotGenerator()
data = PlotData(
    title="{title}",
    xlabel="{xlabel}",
    ylabel="{ylabel}",
    x_data={x_data},
    y_data={y_data},
)
result = generator.create_line_plot(data, PlotFormat.PNG)
print(f"Saved to: {{result.output_path}}")
""",

            "export_table": """# Export table for publication
from src.output.exporters import PublicationExporter, create_table_from_dict

exporter = PublicationExporter()
table = create_table_from_dict(
    data={data},
    title="{title}",
    caption="{caption}",
    label="{label}",
)
result = exporter.export_table(table, 'latex')
print(f"Saved to: {{result.output_path}}")
""",

            "statistical_test": """# Perform statistical test
from scipy import stats

# Two-sample t-test
t_stat, p_value = stats.ttest_ind(group1, group2)
print(f"t-statistic: {{t_stat:.4f}}")
print(f"p-value: {{p_value:.4f}}")

# Interpret results
alpha = 0.05
if p_value < alpha:
    print("Significant difference (reject null hypothesis)")
else:
    print("No significant difference (fail to reject null hypothesis)")
""",
        }

        template = snippets.get(operation, f"# Unknown operation: {operation}")
        return template.format(**kwargs) if kwargs else template


# =============================================================================
# Singleton Pattern
# =============================================================================


_jupyter_instance: Optional[JupyterIntegration] = None


def get_jupyter_integration() -> JupyterIntegration:
    """Get singleton JupyterIntegration instance."""
    global _jupyter_instance
    if _jupyter_instance is None:
        _jupyter_instance = JupyterIntegration()
    return _jupyter_instance


def initialize_jupyter_integration(
    api_base_url: str = "http://localhost:8000/api",
    output_dir: Optional[str] = None,
) -> JupyterIntegration:
    """Initialize JupyterIntegration with custom config."""
    global _jupyter_instance
    _jupyter_instance = JupyterIntegration(
        api_base_url=api_base_url,
        output_dir=output_dir,
    )
    return _jupyter_instance
