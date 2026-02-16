"""
Publication-Quality Plot Generator (S15.5).

Provides matplotlib-based plot generation with IEEE/ACM formatting styles.
Supports:
- Line plots, bar charts, scatter plots, heatmaps
- IEEE and ACM color schemes
- Vector graphics export (PDF, SVG, EPS)
- Automatic styling for publication standards
"""

import io
import base64
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

# Optional matplotlib imports - gracefully handle if not installed
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.figure import Figure
    from matplotlib.axes import Axes
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    Figure = None
    Axes = None

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None


# =============================================================================
# Enumerations
# =============================================================================


class PlotType(str, Enum):
    """Types of plots supported."""
    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    BOX = "box"
    VIOLIN = "violin"
    HISTOGRAM = "histogram"
    PIE = "pie"
    AREA = "area"
    CONFUSION_MATRIX = "confusion_matrix"


class ColorScheme(str, Enum):
    """Publication color schemes."""
    IEEE = "ieee"
    ACM = "acm"
    NATURE = "nature"
    GRAYSCALE = "grayscale"
    COLORBLIND_SAFE = "colorblind_safe"


class PlotFormat(str, Enum):
    """Output formats for plots."""
    PDF = "pdf"
    SVG = "svg"
    PNG = "png"
    EPS = "eps"
    TIFF = "tiff"


# =============================================================================
# Color Palettes
# =============================================================================


COLOR_PALETTES = {
    ColorScheme.IEEE: [
        "#0072B2",  # Blue
        "#D55E00",  # Vermillion
        "#009E73",  # Green
        "#CC79A7",  # Pink
        "#F0E442",  # Yellow
        "#56B4E9",  # Sky Blue
        "#E69F00",  # Orange
        "#000000",  # Black
    ],
    ColorScheme.ACM: [
        "#1f77b4",  # Blue
        "#ff7f0e",  # Orange
        "#2ca02c",  # Green
        "#d62728",  # Red
        "#9467bd",  # Purple
        "#8c564b",  # Brown
        "#e377c2",  # Pink
        "#7f7f7f",  # Gray
    ],
    ColorScheme.NATURE: [
        "#E64B35",  # Red
        "#4DBBD5",  # Cyan
        "#00A087",  # Teal
        "#3C5488",  # Blue
        "#F39B7F",  # Salmon
        "#8491B4",  # Gray Blue
        "#91D1C2",  # Light Teal
        "#DC0000",  # Dark Red
    ],
    ColorScheme.GRAYSCALE: [
        "#000000",
        "#404040",
        "#808080",
        "#A0A0A0",
        "#C0C0C0",
        "#E0E0E0",
    ],
    ColorScheme.COLORBLIND_SAFE: [
        "#0077BB",  # Blue
        "#CC3311",  # Red
        "#009988",  # Teal
        "#EE7733",  # Orange
        "#33BBEE",  # Cyan
        "#EE3377",  # Magenta
        "#BBBBBB",  # Gray
    ],
}


# =============================================================================
# Data Models
# =============================================================================


class PlotStyle(BaseModel):
    """Plot styling configuration."""
    # Figure size (inches)
    width: float = 3.5  # IEEE single column
    height: float = 2.5
    dpi: int = 300

    # Font settings
    font_family: str = "serif"
    font_size: int = 9
    title_size: int = 10
    label_size: int = 9
    tick_size: int = 8
    legend_size: int = 8

    # Line settings
    line_width: float = 1.5
    marker_size: float = 4.0

    # Grid
    show_grid: bool = True
    grid_alpha: float = 0.3
    grid_style: str = "--"

    # Legend
    legend_location: str = "best"
    legend_frameon: bool = True

    # Color scheme
    color_scheme: ColorScheme = ColorScheme.IEEE

    # Borders
    spine_width: float = 0.8

    @classmethod
    def ieee_single_column(cls) -> "PlotStyle":
        """IEEE single column style (3.5 inches wide)."""
        return cls(width=3.5, height=2.5, font_size=9)

    @classmethod
    def ieee_double_column(cls) -> "PlotStyle":
        """IEEE double column style (7 inches wide)."""
        return cls(width=7.0, height=3.5, font_size=10)

    @classmethod
    def acm_single_column(cls) -> "PlotStyle":
        """ACM single column style."""
        return cls(
            width=3.33,
            height=2.5,
            font_size=8,
            color_scheme=ColorScheme.ACM,
        )

    @classmethod
    def acm_double_column(cls) -> "PlotStyle":
        """ACM double column style."""
        return cls(
            width=7.0,
            height=3.5,
            font_size=9,
            color_scheme=ColorScheme.ACM,
        )

    @classmethod
    def presentation(cls) -> "PlotStyle":
        """Presentation style (larger fonts)."""
        return cls(
            width=10,
            height=6,
            font_size=14,
            title_size=16,
            label_size=14,
            tick_size=12,
            legend_size=12,
            line_width=2.5,
            marker_size=8,
        )


class PlotData(BaseModel):
    """Data for a plot."""
    plot_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    xlabel: str = ""
    ylabel: str = ""

    # Data series
    x_data: list[Any] = Field(default_factory=list)
    y_data: list[Any] = Field(default_factory=list)  # Can be list of lists for multiple series
    labels: list[str] = Field(default_factory=list)  # Series labels

    # Optional data
    errors: Optional[list[Any]] = None  # Error bars
    colors: Optional[list[str]] = None  # Custom colors
    markers: Optional[list[str]] = None  # Custom markers

    # For heatmaps/confusion matrices
    matrix_data: Optional[list[list[float]]] = None
    row_labels: Optional[list[str]] = None
    col_labels: Optional[list[str]] = None

    # Annotations
    annotations: list[dict[str, Any]] = Field(default_factory=list)

    # Legend
    show_legend: bool = True

    # Axis limits
    xlim: Optional[tuple[float, float]] = None
    ylim: Optional[tuple[float, float]] = None


class PlotResult(BaseModel):
    """Result of plot generation."""
    success: bool
    plot_id: str
    output_path: Optional[str] = None
    format: PlotFormat
    file_size_bytes: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    base64_data: Optional[str] = None  # For inline embedding
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Plot Generator
# =============================================================================


class PlotGenerator:
    """
    Publication-quality plot generator.

    S15.5: Generates matplotlib plots with IEEE/ACM formatting.
    """

    def __init__(
        self,
        style: Optional[PlotStyle] = None,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize plot generator.

        Args:
            style: Default plot style
            output_dir: Directory for saving plots
        """
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError(
                "matplotlib is required for PlotGenerator. "
                "Install with: pip install matplotlib"
            )

        self.style = style or PlotStyle.ieee_single_column()
        self.output_dir = Path(output_dir or "exports/figures")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Plot history
        self._plots: list[PlotResult] = []

    def _apply_style(self, fig: "Figure", ax: "Axes") -> None:
        """Apply publication style to figure and axes."""
        style = self.style
        colors = COLOR_PALETTES[style.color_scheme]

        # Set color cycle
        ax.set_prop_cycle(color=colors)

        # Font settings
        plt.rcParams.update({
            "font.family": style.font_family,
            "font.size": style.font_size,
            "axes.titlesize": style.title_size,
            "axes.labelsize": style.label_size,
            "xtick.labelsize": style.tick_size,
            "ytick.labelsize": style.tick_size,
            "legend.fontsize": style.legend_size,
        })

        # Grid
        if style.show_grid:
            ax.grid(True, alpha=style.grid_alpha, linestyle=style.grid_style)

        # Spines
        for spine in ax.spines.values():
            spine.set_linewidth(style.spine_width)

    def _save_figure(
        self,
        fig: "Figure",
        filename: str,
        format: PlotFormat,
    ) -> PlotResult:
        """Save figure to file."""
        output_path = self.output_dir / f"{filename}.{format.value}"

        fig.savefig(
            output_path,
            format=format.value,
            dpi=self.style.dpi,
            bbox_inches="tight",
            pad_inches=0.1,
        )

        # Get base64 for embedding
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=self.style.dpi, bbox_inches="tight")
        buf.seek(0)
        base64_data = base64.b64encode(buf.read()).decode("utf-8")

        plt.close(fig)

        result = PlotResult(
            success=True,
            plot_id=str(uuid4()),
            output_path=str(output_path),
            format=format,
            file_size_bytes=output_path.stat().st_size,
            base64_data=base64_data,
        )

        self._plots.append(result)
        return result

    # -------------------------------------------------------------------------
    # Line Plot
    # -------------------------------------------------------------------------

    def create_line_plot(
        self,
        data: PlotData,
        format: PlotFormat = PlotFormat.PDF,
        filename: Optional[str] = None,
        style: Optional[PlotStyle] = None,
    ) -> PlotResult:
        """
        Create a line plot.

        Args:
            data: Plot data
            format: Output format
            filename: Output filename (without extension)
            style: Override style

        Returns:
            PlotResult with file path and metadata
        """
        if style:
            self.style = style

        fig, ax = plt.subplots(figsize=(self.style.width, self.style.height))
        self._apply_style(fig, ax)

        colors = COLOR_PALETTES[self.style.color_scheme]
        markers = data.markers or ["o", "s", "^", "D", "v", "<", ">", "p"]

        # Handle multiple series
        y_data = data.y_data
        if y_data and not isinstance(y_data[0], (list, tuple)):
            y_data = [y_data]

        labels = data.labels or [f"Series {i+1}" for i in range(len(y_data))]

        for i, (y, label) in enumerate(zip(y_data, labels)):
            color = data.colors[i] if data.colors and i < len(data.colors) else colors[i % len(colors)]
            marker = markers[i % len(markers)]

            ax.plot(
                data.x_data,
                y,
                label=label,
                color=color,
                linewidth=self.style.line_width,
                marker=marker,
                markersize=self.style.marker_size,
            )

            # Error bars if provided
            if data.errors and i < len(data.errors):
                ax.fill_between(
                    data.x_data,
                    [yi - e for yi, e in zip(y, data.errors[i])],
                    [yi + e for yi, e in zip(y, data.errors[i])],
                    alpha=0.2,
                    color=color,
                )

        ax.set_title(data.title)
        ax.set_xlabel(data.xlabel)
        ax.set_ylabel(data.ylabel)

        if data.xlim:
            ax.set_xlim(data.xlim)
        if data.ylim:
            ax.set_ylim(data.ylim)

        if data.show_legend and len(y_data) > 1:
            ax.legend(loc=self.style.legend_location, frameon=self.style.legend_frameon)

        # Annotations
        for ann in data.annotations:
            ax.annotate(**ann)

        filename = filename or f"line_plot_{data.plot_id[:8]}"
        return self._save_figure(fig, filename, format)

    # -------------------------------------------------------------------------
    # Bar Plot
    # -------------------------------------------------------------------------

    def create_bar_plot(
        self,
        data: PlotData,
        format: PlotFormat = PlotFormat.PDF,
        filename: Optional[str] = None,
        horizontal: bool = False,
        grouped: bool = False,
    ) -> PlotResult:
        """
        Create a bar plot.

        Args:
            data: Plot data
            format: Output format
            filename: Output filename
            horizontal: Horizontal bars
            grouped: Grouped bar chart

        Returns:
            PlotResult
        """
        fig, ax = plt.subplots(figsize=(self.style.width, self.style.height))
        self._apply_style(fig, ax)

        colors = COLOR_PALETTES[self.style.color_scheme]

        y_data = data.y_data
        if y_data and not isinstance(y_data[0], (list, tuple)):
            y_data = [y_data]

        labels = data.labels or [f"Series {i+1}" for i in range(len(y_data))]
        x = range(len(data.x_data))

        if grouped and len(y_data) > 1:
            # Grouped bar chart
            width = 0.8 / len(y_data)
            for i, (y, label) in enumerate(zip(y_data, labels)):
                offset = (i - len(y_data) / 2 + 0.5) * width
                positions = [xi + offset for xi in x]
                color = colors[i % len(colors)]

                if horizontal:
                    ax.barh(positions, y, height=width, label=label, color=color)
                else:
                    ax.bar(positions, y, width=width, label=label, color=color)
        else:
            # Simple bar chart
            y = y_data[0] if y_data else []
            bar_colors = data.colors or [colors[i % len(colors)] for i in range(len(y))]

            if horizontal:
                ax.barh(x, y, color=bar_colors)
            else:
                ax.bar(x, y, color=bar_colors)

        if horizontal:
            ax.set_yticks(list(x))
            ax.set_yticklabels(data.x_data)
            ax.set_xlabel(data.ylabel)
            ax.set_ylabel(data.xlabel)
        else:
            ax.set_xticks(list(x))
            ax.set_xticklabels(data.x_data, rotation=45, ha="right")
            ax.set_xlabel(data.xlabel)
            ax.set_ylabel(data.ylabel)

        ax.set_title(data.title)

        if data.show_legend and len(y_data) > 1:
            ax.legend(loc=self.style.legend_location, frameon=self.style.legend_frameon)

        fig.tight_layout()

        filename = filename or f"bar_plot_{data.plot_id[:8]}"
        return self._save_figure(fig, filename, format)

    # -------------------------------------------------------------------------
    # Scatter Plot
    # -------------------------------------------------------------------------

    def create_scatter_plot(
        self,
        data: PlotData,
        format: PlotFormat = PlotFormat.PDF,
        filename: Optional[str] = None,
        sizes: Optional[list[float]] = None,
    ) -> PlotResult:
        """
        Create a scatter plot.

        Args:
            data: Plot data
            format: Output format
            filename: Output filename
            sizes: Point sizes (for bubble charts)

        Returns:
            PlotResult
        """
        fig, ax = plt.subplots(figsize=(self.style.width, self.style.height))
        self._apply_style(fig, ax)

        colors = COLOR_PALETTES[self.style.color_scheme]

        y_data = data.y_data
        if y_data and not isinstance(y_data[0], (list, tuple)):
            y_data = [y_data]

        labels = data.labels or [f"Series {i+1}" for i in range(len(y_data))]

        for i, (y, label) in enumerate(zip(y_data, labels)):
            color = data.colors[i] if data.colors and i < len(data.colors) else colors[i % len(colors)]
            s = sizes[i] if sizes and i < len(sizes) else self.style.marker_size ** 2 * 10

            ax.scatter(
                data.x_data,
                y,
                label=label,
                color=color,
                s=s,
                alpha=0.7,
            )

        ax.set_title(data.title)
        ax.set_xlabel(data.xlabel)
        ax.set_ylabel(data.ylabel)

        if data.xlim:
            ax.set_xlim(data.xlim)
        if data.ylim:
            ax.set_ylim(data.ylim)

        if data.show_legend and len(y_data) > 1:
            ax.legend(loc=self.style.legend_location, frameon=self.style.legend_frameon)

        filename = filename or f"scatter_plot_{data.plot_id[:8]}"
        return self._save_figure(fig, filename, format)

    # -------------------------------------------------------------------------
    # Heatmap / Confusion Matrix
    # -------------------------------------------------------------------------

    def create_heatmap(
        self,
        data: PlotData,
        format: PlotFormat = PlotFormat.PDF,
        filename: Optional[str] = None,
        cmap: str = "Blues",
        annotate: bool = True,
        fmt: str = ".2f",
    ) -> PlotResult:
        """
        Create a heatmap or confusion matrix.

        Args:
            data: Plot data (use matrix_data, row_labels, col_labels)
            format: Output format
            filename: Output filename
            cmap: Colormap name
            annotate: Show values in cells
            fmt: Number format for annotations

        Returns:
            PlotResult
        """
        if not data.matrix_data:
            raise ValueError("matrix_data is required for heatmap")

        fig, ax = plt.subplots(figsize=(self.style.width, self.style.height))
        self._apply_style(fig, ax)

        matrix = data.matrix_data
        if NUMPY_AVAILABLE:
            matrix = np.array(matrix)

        im = ax.imshow(matrix, cmap=cmap, aspect="auto")

        # Colorbar
        cbar = fig.colorbar(im, ax=ax)
        cbar.ax.tick_params(labelsize=self.style.tick_size)

        # Labels
        if data.row_labels:
            ax.set_yticks(range(len(data.row_labels)))
            ax.set_yticklabels(data.row_labels)
        if data.col_labels:
            ax.set_xticks(range(len(data.col_labels)))
            ax.set_xticklabels(data.col_labels, rotation=45, ha="right")

        # Annotations
        if annotate:
            for i in range(len(matrix)):
                for j in range(len(matrix[0])):
                    value = matrix[i][j]
                    text_color = "white" if value > (max(max(row) for row in matrix) / 2) else "black"
                    ax.text(j, i, f"{value:{fmt}}", ha="center", va="center", color=text_color, fontsize=self.style.tick_size)

        ax.set_title(data.title)
        ax.set_xlabel(data.xlabel)
        ax.set_ylabel(data.ylabel)

        fig.tight_layout()

        filename = filename or f"heatmap_{data.plot_id[:8]}"
        return self._save_figure(fig, filename, format)

    def create_confusion_matrix(
        self,
        data: PlotData,
        format: PlotFormat = PlotFormat.PDF,
        filename: Optional[str] = None,
        normalize: bool = False,
    ) -> PlotResult:
        """
        Create a confusion matrix plot.

        Args:
            data: Plot data with matrix_data
            format: Output format
            filename: Output filename
            normalize: Normalize values

        Returns:
            PlotResult
        """
        if not data.matrix_data:
            raise ValueError("matrix_data is required for confusion matrix")

        matrix = data.matrix_data

        if normalize and NUMPY_AVAILABLE:
            matrix = np.array(matrix)
            matrix = matrix / matrix.sum(axis=1, keepdims=True)
            matrix = matrix.tolist()

        # Determine if matrix contains integers or floats
        is_integer_matrix = all(
            isinstance(val, int) for row in matrix for val in row
        )

        data.matrix_data = matrix
        return self.create_heatmap(
            data,
            format=format,
            filename=filename,
            cmap="Blues",
            annotate=True,
            fmt=".0f" if is_integer_matrix else ".2f",
        )

    # -------------------------------------------------------------------------
    # Box Plot
    # -------------------------------------------------------------------------

    def create_box_plot(
        self,
        data: PlotData,
        format: PlotFormat = PlotFormat.PDF,
        filename: Optional[str] = None,
        show_outliers: bool = True,
    ) -> PlotResult:
        """
        Create a box plot.

        Args:
            data: Plot data (y_data should be list of lists)
            format: Output format
            filename: Output filename
            show_outliers: Show outlier points

        Returns:
            PlotResult
        """
        fig, ax = plt.subplots(figsize=(self.style.width, self.style.height))
        self._apply_style(fig, ax)

        colors = COLOR_PALETTES[self.style.color_scheme]

        y_data = data.y_data
        if y_data and not isinstance(y_data[0], (list, tuple)):
            y_data = [y_data]

        bp = ax.boxplot(
            y_data,
            tick_labels=data.x_data or data.labels,
            patch_artist=True,
            showfliers=show_outliers,
        )

        # Color boxes
        for i, box in enumerate(bp["boxes"]):
            box.set_facecolor(colors[i % len(colors)])
            box.set_alpha(0.7)

        ax.set_title(data.title)
        ax.set_xlabel(data.xlabel)
        ax.set_ylabel(data.ylabel)

        if data.ylim:
            ax.set_ylim(data.ylim)

        fig.tight_layout()

        filename = filename or f"box_plot_{data.plot_id[:8]}"
        return self._save_figure(fig, filename, format)

    # -------------------------------------------------------------------------
    # Histogram
    # -------------------------------------------------------------------------

    def create_histogram(
        self,
        data: PlotData,
        format: PlotFormat = PlotFormat.PDF,
        filename: Optional[str] = None,
        bins: int = 20,
        density: bool = False,
    ) -> PlotResult:
        """
        Create a histogram.

        Args:
            data: Plot data
            format: Output format
            filename: Output filename
            bins: Number of bins
            density: Normalize to density

        Returns:
            PlotResult
        """
        fig, ax = plt.subplots(figsize=(self.style.width, self.style.height))
        self._apply_style(fig, ax)

        colors = COLOR_PALETTES[self.style.color_scheme]

        y_data = data.y_data
        if y_data and not isinstance(y_data[0], (list, tuple)):
            y_data = [y_data]

        labels = data.labels or [f"Series {i+1}" for i in range(len(y_data))]

        for i, (y, label) in enumerate(zip(y_data, labels)):
            color = colors[i % len(colors)]
            ax.hist(
                y,
                bins=bins,
                label=label,
                color=color,
                alpha=0.7,
                density=density,
                edgecolor="white",
            )

        ax.set_title(data.title)
        ax.set_xlabel(data.xlabel)
        ax.set_ylabel("Density" if density else "Frequency")

        if data.show_legend and len(y_data) > 1:
            ax.legend(loc=self.style.legend_location, frameon=self.style.legend_frameon)

        fig.tight_layout()

        filename = filename or f"histogram_{data.plot_id[:8]}"
        return self._save_figure(fig, filename, format)

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_plot_history(self) -> list[PlotResult]:
        """Get history of generated plots."""
        return self._plots.copy()

    def get_stats(self) -> dict[str, Any]:
        """Get plot generation statistics."""
        total_size = sum(p.file_size_bytes for p in self._plots)
        format_counts = {}
        for plot in self._plots:
            fmt = plot.format.value
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

        return {
            "total_plots": len(self._plots),
            "total_size_bytes": total_size,
            "format_breakdown": format_counts,
            "output_directory": str(self.output_dir),
        }


# =============================================================================
# Convenience Functions
# =============================================================================


def create_comparison_plot(
    methods: list[str],
    metrics: dict[str, list[float]],
    title: str = "Method Comparison",
    format: PlotFormat = PlotFormat.PDF,
    style: Optional[PlotStyle] = None,
) -> PlotResult:
    """
    Create a grouped bar chart comparing methods across metrics.

    Args:
        methods: List of method names
        metrics: Dict mapping metric names to values for each method
        title: Plot title
        format: Output format
        style: Plot style

    Returns:
        PlotResult
    """
    generator = PlotGenerator(style=style or PlotStyle.ieee_single_column())

    data = PlotData(
        title=title,
        xlabel="Method",
        ylabel="Score",
        x_data=methods,
        y_data=list(metrics.values()),
        labels=list(metrics.keys()),
    )

    return generator.create_bar_plot(data, format=format, grouped=True)


def create_training_curve(
    epochs: list[int],
    train_loss: list[float],
    val_loss: Optional[list[float]] = None,
    title: str = "Training Curve",
    format: PlotFormat = PlotFormat.PDF,
) -> PlotResult:
    """
    Create a training curve plot.

    Args:
        epochs: Epoch numbers
        train_loss: Training loss values
        val_loss: Validation loss values
        title: Plot title
        format: Output format

    Returns:
        PlotResult
    """
    generator = PlotGenerator()

    y_data = [train_loss]
    labels = ["Training Loss"]

    if val_loss:
        y_data.append(val_loss)
        labels.append("Validation Loss")

    data = PlotData(
        title=title,
        xlabel="Epoch",
        ylabel="Loss",
        x_data=epochs,
        y_data=y_data,
        labels=labels,
    )

    return generator.create_line_plot(data, format=format)


# =============================================================================
# Check Availability
# =============================================================================


def is_plotting_available() -> bool:
    """Check if plotting dependencies are available."""
    return MATPLOTLIB_AVAILABLE


def get_missing_dependencies() -> list[str]:
    """Get list of missing plotting dependencies."""
    missing = []
    if not MATPLOTLIB_AVAILABLE:
        missing.append("matplotlib")
    if not NUMPY_AVAILABLE:
        missing.append("numpy")
    return missing
