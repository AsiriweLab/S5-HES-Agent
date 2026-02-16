"""
Tests for Publication Exporter (S15.1).

Tests:
- PublicationExporter initialization
- LaTeX table generation
- BibTeX citation generation
- Methodology section generation
- CSV/JSON export
- Publication package export
- Format generators
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime


class TestPublicationExporterCore:
    """Test core PublicationExporter functionality."""

    def test_exporter_initialization(self):
        """Test exporter initializes correctly."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            ExportConfig,
            PublicationFormat,
        )

        config = ExportConfig(
            publication_format=PublicationFormat.IEEE,
            output_directory="test_exports",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config.output_directory = tmpdir
            exporter = PublicationExporter(config)

            assert exporter is not None
            assert exporter.config.publication_format == PublicationFormat.IEEE

    def test_exporter_default_config(self):
        """Test exporter with default configuration."""
        from src.output.exporters.publication_exporter import PublicationExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            stats = exporter.get_export_stats()
            assert stats["total_exports"] == 0

    def test_export_config_fields(self):
        """Test ExportConfig fields and defaults."""
        from src.output.exporters.publication_exporter import (
            ExportConfig,
            PublicationFormat,
            TableStyle,
            FigureStyle,
            ExportFormat,
        )

        config = ExportConfig()

        assert config.publication_format == PublicationFormat.IEEE
        assert config.include_timestamps is True
        assert config.include_provenance is True
        assert config.figure_dpi == 300
        assert config.table_style == TableStyle.IEEE_STANDARD


class TestTableExport:
    """Test table export functionality."""

    def test_latex_table_generation(self):
        """Test LaTeX table generation."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            TableData,
            TableColumn,
            TableStyle,
            ExportFormat,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            table = TableData(
                title="Test Results",
                caption="Comparison of detection accuracy across methods",
                label="tab:results",
                columns=[
                    TableColumn(name="method", header="Method", alignment="l"),
                    TableColumn(name="accuracy", header="Accuracy", alignment="c", format_spec=".2f"),
                    TableColumn(name="f1_score", header="F1 Score", alignment="c", format_spec=".3f"),
                ],
                rows=[
                    {"method": "Baseline", "accuracy": 0.85, "f1_score": 0.823},
                    {"method": "S5-HES", "accuracy": 0.92, "f1_score": 0.915},
                ],
            )

            result = exporter.export_table(table, ExportFormat.LATEX)

            assert result.success
            assert result.export_format == ExportFormat.LATEX
            assert Path(result.output_path).exists()

            content = Path(result.output_path).read_text()
            assert r"\begin{table}" in content
            assert r"\caption{" in content
            assert r"\label{tab:results}" in content
            assert "Method" in content
            assert "Accuracy" in content

    def test_markdown_table_generation(self):
        """Test Markdown table generation."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            TableData,
            TableColumn,
            ExportFormat,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            table = TableData(
                title="Performance Metrics",
                caption="Summary of simulation results",
                label="tab:metrics",
                columns=[
                    TableColumn(name="metric", header="Metric", alignment="l"),
                    TableColumn(name="value", header="Value", alignment="r"),
                ],
                rows=[
                    {"metric": "Throughput", "value": "1000 events/s"},
                    {"metric": "Latency", "value": "5ms"},
                ],
            )

            result = exporter.export_table(table, ExportFormat.MARKDOWN)

            assert result.success
            content = Path(result.output_path).read_text()
            assert "| Metric | Value |" in content
            assert "| Throughput | 1000 events/s |" in content

    def test_csv_table_generation(self):
        """Test CSV table generation."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            TableData,
            TableColumn,
            ExportFormat,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            table = TableData(
                title="Data Export",
                caption="Raw data",
                label="tab:data",
                columns=[
                    TableColumn(name="id", header="ID"),
                    TableColumn(name="name", header="Name"),
                ],
                rows=[
                    {"id": 1, "name": "Device A"},
                    {"id": 2, "name": "Device B"},
                ],
            )

            result = exporter.export_table(table, ExportFormat.CSV)

            assert result.success
            content = Path(result.output_path).read_text()
            assert "ID,Name" in content
            assert "1,Device A" in content

    def test_booktabs_style(self):
        """Test booktabs table style."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            TableData,
            TableColumn,
            TableStyle,
            ExportFormat,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            table = TableData(
                title="Booktabs Table",
                caption="Professional table with booktabs",
                label="tab:booktabs",
                columns=[
                    TableColumn(name="col1", header="Column 1"),
                    TableColumn(name="col2", header="Column 2"),
                ],
                rows=[{"col1": "A", "col2": "B"}],
            )

            result = exporter.export_table(table, ExportFormat.LATEX, TableStyle.BOOKTABS)

            content = Path(result.output_path).read_text()
            assert r"\toprule" in content
            assert r"\midrule" in content
            assert r"\bottomrule" in content


class TestCitationExport:
    """Test BibTeX citation export."""

    def test_citation_model(self):
        """Test Citation model and BibTeX conversion."""
        from src.output.exporters.publication_exporter import Citation

        citation = Citation(
            cite_key="smith2023",
            entry_type="article",
            title="Smart Home Security Analysis",
            author="Smith, John and Doe, Jane",
            year=2023,
            journal="IEEE IoT Journal",
            volume="10",
            number="3",
            pages="100-115",
            doi="10.1109/IOT.2023.123456",
        )

        bibtex = citation.to_bibtex()

        assert "@article{smith2023," in bibtex
        assert "title = {Smart Home Security Analysis}" in bibtex
        assert "author = {Smith, John and Doe, Jane}" in bibtex
        assert "journal = {IEEE IoT Journal}" in bibtex

    def test_export_citations(self):
        """Test exporting multiple citations."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            Citation,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            citations = [
                Citation(
                    cite_key="ref1",
                    entry_type="article",
                    title="First Paper",
                    author="Author One",
                    year=2023,
                ),
                Citation(
                    cite_key="ref2",
                    entry_type="inproceedings",
                    title="Second Paper",
                    author="Author Two",
                    year=2024,
                    booktitle="Conference X",
                ),
            ]

            result = exporter.export_citations(citations)

            assert result.success
            assert result.metadata["citation_count"] == 2

            content = Path(result.output_path).read_text()
            assert "@article{ref1," in content
            assert "@inproceedings{ref2," in content

    def test_self_citation_generation(self):
        """Test S5-HES self-citation generation."""
        from src.output.exporters.publication_exporter import PublicationExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            citation = exporter.generate_self_citation()

            assert citation.cite_key == "s5hes2024"
            assert "S5-HES" in citation.title
            assert citation.year == datetime.now().year


class TestMethodologyExport:
    """Test methodology section export."""

    def test_methodology_model(self):
        """Test MethodologySection model."""
        from src.output.exporters.publication_exporter import MethodologySection

        methodology = MethodologySection(
            experiment_name="Security Test",
            experiment_description="Testing IoT device security",
            home_configuration={"rooms": 5, "devices": 20},
            simulation_parameters={"duration": "24h", "time_compression": 1440},
            threat_scenarios=[
                {"name": "DDoS", "type": "network"},
                {"name": "Credential Theft", "type": "authentication"},
            ],
            random_seeds={"main": 42},
        )

        assert methodology.experiment_name == "Security Test"
        assert len(methodology.threat_scenarios) == 2

        # Test hash computation
        hash1 = methodology.compute_hash()
        assert len(hash1) == 12

        # Same config should give same hash
        hash2 = methodology.compute_hash()
        assert hash1 == hash2

    def test_methodology_latex_export(self):
        """Test methodology LaTeX export."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            MethodologySection,
            ExportFormat,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            methodology = MethodologySection(
                experiment_name="IoT Security Evaluation",
                experiment_description="Comprehensive security assessment",
                home_configuration={"type": "apartment", "rooms": 3},
                simulation_parameters={"duration": "7d"},
                threat_scenarios=[{"name": "Malware", "type": "malware"}],
                software_versions={"Python": "3.11", "S5-HES": "1.0"},
                random_seeds={"numpy": 42, "torch": 42},
            )

            result = exporter.export_methodology(methodology, ExportFormat.LATEX)

            assert result.success
            content = Path(result.output_path).read_text()

            assert r"\section{Methodology}" in content
            assert "IoT Security Evaluation" in content or "Experiment" in content
            assert r"\subsection{Reproducibility}" in content
            assert "Configuration hash" in content

    def test_methodology_markdown_export(self):
        """Test methodology Markdown export."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            MethodologySection,
            ExportFormat,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            methodology = MethodologySection(
                experiment_name="Test Experiment",
                home_configuration={"devices": 10},
            )

            result = exporter.export_methodology(methodology, ExportFormat.MARKDOWN)

            assert result.success
            content = Path(result.output_path).read_text()
            assert "# Methodology" in content


class TestDataExport:
    """Test data export functionality."""

    def test_json_export(self):
        """Test JSON results export."""
        from src.output.exporters.publication_exporter import PublicationExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            results = {
                "accuracy": 0.95,
                "precision": 0.93,
                "recall": 0.97,
                "metrics": [1, 2, 3],
            }

            result = exporter.export_results_json(results)

            assert result.success
            content = json.loads(Path(result.output_path).read_text())

            assert content["accuracy"] == 0.95
            assert "_export_metadata" in content

    def test_json_export_without_metadata(self):
        """Test JSON export without metadata."""
        from src.output.exporters.publication_exporter import PublicationExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            results = {"data": [1, 2, 3]}
            result = exporter.export_results_json(results, include_metadata=False)

            content = json.loads(Path(result.output_path).read_text())
            assert "_export_metadata" not in content


class TestFigureExport:
    """Test figure export functionality."""

    def test_figure_latex_export(self):
        """Test LaTeX figure inclusion code generation."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            FigureData,
            FigureStyle,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            figure = FigureData(
                title="Results Plot",
                caption="Detection accuracy over time",
                label="fig:accuracy",
                file_path="figures/accuracy.pdf",
                width=r"\columnwidth",
            )

            result = exporter.export_figure_latex(figure)

            assert result.success
            content = Path(result.output_path).read_text()

            assert r"\begin{figure}" in content
            assert r"\includegraphics" in content
            assert r"\caption{" in content
            assert r"\label{fig:accuracy}" in content

    def test_figure_double_column_style(self):
        """Test double-column figure style."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            FigureData,
            FigureStyle,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            figure = FigureData(
                title="Wide Figure",
                caption="Full-width figure",
                label="fig:wide",
                file_path="figures/wide.pdf",
            )

            result = exporter.export_figure_latex(figure, FigureStyle.IEEE_DOUBLE_COLUMN)

            content = Path(result.output_path).read_text()
            assert r"\begin{figure*}" in content
            assert r"\end{figure*}" in content


class TestPublicationPackage:
    """Test complete publication package export."""

    def test_export_publication_package(self):
        """Test exporting a complete publication package."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            TableData,
            TableColumn,
            FigureData,
            MethodologySection,
            Citation,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            # Create test data
            tables = [
                TableData(
                    title="Results",
                    caption="Main results",
                    label="tab:main",
                    columns=[TableColumn(name="x", header="X")],
                    rows=[{"x": 1}],
                )
            ]

            figures = [
                FigureData(
                    title="Plot",
                    caption="Test plot",
                    label="fig:test",
                    file_path="test.pdf",
                )
            ]

            methodology = MethodologySection(
                experiment_name="Test",
                home_configuration={"rooms": 1},
            )

            citations = [
                Citation(
                    cite_key="test",
                    entry_type="misc",
                    title="Test",
                    author="Author",
                    year=2024,
                )
            ]

            results = {"score": 0.95}

            # Export package
            export_results = exporter.export_publication_package(
                tables=tables,
                figures=figures,
                methodology=methodology,
                citations=citations,
                results=results,
                package_name="test_package",
            )

            assert len(export_results) >= 4  # At least table, figure, methodology, citations

            # Check package structure
            package_dir = Path(tmpdir) / "test_package"
            assert package_dir.exists()
            assert (package_dir / "manifest.json").exists()
            assert (package_dir / "tables").exists()
            assert (package_dir / "figures").exists()


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_create_table_from_dict(self):
        """Test creating TableData from dictionaries."""
        from src.output.exporters.publication_exporter import create_table_from_dict

        data = [
            {"name": "A", "value": 10},
            {"name": "B", "value": 20},
        ]

        table = create_table_from_dict(
            data=data,
            title="Test Table",
            caption="A test table",
            label="tab:test",
        )

        assert table.title == "Test Table"
        assert len(table.columns) == 2
        assert len(table.rows) == 2
        assert table.columns[0].name == "name"
        assert table.columns[1].name == "value"

    def test_create_table_with_column_config(self):
        """Test creating TableData with custom column config."""
        from src.output.exporters.publication_exporter import create_table_from_dict

        data = [{"score": 0.95}]

        table = create_table_from_dict(
            data=data,
            title="Scores",
            caption="Test scores",
            label="tab:scores",
            column_config={
                "score": {"header": "Accuracy Score", "alignment": "r", "format_spec": ".2%"},
            },
        )

        assert table.columns[0].header == "Accuracy Score"
        assert table.columns[0].alignment == "r"
        assert table.columns[0].format_spec == ".2%"

    def test_create_methodology_from_experiment(self):
        """Test creating MethodologySection from experiment data."""
        from src.output.exporters.publication_exporter import create_methodology_from_experiment

        methodology = create_methodology_from_experiment(
            experiment_name="Security Test",
            home_config={"rooms": 5, "devices": 15},
            simulation_params={"duration": "24h"},
            threat_scenarios=[{"name": "DDoS", "type": "network"}],
            random_seed=42,
            description="Testing security features",
        )

        assert methodology.experiment_name == "Security Test"
        assert methodology.experiment_description == "Testing security features"
        assert methodology.random_seeds["main_seed"] == 42
        assert "Python" in methodology.software_versions


class TestExportStatistics:
    """Test export statistics and history."""

    def test_export_history(self):
        """Test export history tracking."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            TableData,
            TableColumn,
            ExportFormat,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            # Export multiple items
            table = TableData(
                title="Test",
                caption="Test",
                label="tab:test",
                columns=[TableColumn(name="x", header="X")],
                rows=[{"x": 1}],
            )

            exporter.export_table(table, ExportFormat.LATEX)
            exporter.export_table(table, ExportFormat.CSV)

            history = exporter.get_export_history()
            assert len(history) == 2

    def test_export_stats(self):
        """Test export statistics."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            TableData,
            TableColumn,
            ExportFormat,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            table = TableData(
                title="Test",
                caption="Test",
                label="tab:test",
                columns=[TableColumn(name="x", header="X")],
                rows=[{"x": 1}],
            )

            exporter.export_table(table, ExportFormat.LATEX)
            exporter.export_table(table, ExportFormat.CSV)

            stats = exporter.get_export_stats()

            assert stats["total_exports"] == 2
            assert stats["total_size_bytes"] > 0
            assert "latex" in stats["format_breakdown"]
            assert "csv" in stats["format_breakdown"]

    def test_clear_history(self):
        """Test clearing export history."""
        from src.output.exporters.publication_exporter import (
            PublicationExporter,
            TableData,
            TableColumn,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = PublicationExporter()
            exporter.output_dir = Path(tmpdir)

            table = TableData(
                title="Test",
                caption="Test",
                label="tab:test",
                columns=[TableColumn(name="x", header="X")],
                rows=[{"x": 1}],
            )

            exporter.export_table(table)
            assert len(exporter.get_export_history()) == 1

            exporter.clear_history()
            assert len(exporter.get_export_history()) == 0


class TestSingletonAndFactories:
    """Test singleton and factory functions."""

    def test_get_publication_exporter(self):
        """Test getting singleton exporter."""
        from src.output.exporters.publication_exporter import (
            get_publication_exporter,
            initialize_publication_exporter,
            ExportConfig,
        )
        import src.output.exporters.publication_exporter as module

        # Reset singleton
        module._exporter_instance = None

        exporter1 = get_publication_exporter()
        exporter2 = get_publication_exporter()

        assert exporter1 is exporter2

    def test_initialize_publication_exporter(self):
        """Test initializing exporter with custom config."""
        from src.output.exporters.publication_exporter import (
            initialize_publication_exporter,
            ExportConfig,
            PublicationFormat,
        )
        import src.output.exporters.publication_exporter as module

        # Reset singleton
        module._exporter_instance = None

        config = ExportConfig(publication_format=PublicationFormat.ACM)
        exporter = initialize_publication_exporter(config)

        assert exporter.config.publication_format == PublicationFormat.ACM


# =============================================================================
# Plot Generator Tests (S15.5)
# =============================================================================


class TestPlotGeneratorCore:
    """Test PlotGenerator core functionality."""

    def test_plot_generator_initialization(self):
        """Test PlotGenerator initializes correctly."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotStyle,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)
            assert generator is not None
            assert generator.output_dir.exists()

    def test_plot_style_presets(self):
        """Test PlotStyle preset configurations."""
        from src.output.exporters.plot_generator import PlotStyle, ColorScheme

        # IEEE single column
        ieee_single = PlotStyle.ieee_single_column()
        assert ieee_single.width == 3.5
        assert ieee_single.font_size == 9

        # IEEE double column
        ieee_double = PlotStyle.ieee_double_column()
        assert ieee_double.width == 7.0

        # ACM single column
        acm_single = PlotStyle.acm_single_column()
        assert acm_single.width == 3.33
        assert acm_single.color_scheme == ColorScheme.ACM

        # Presentation style
        presentation = PlotStyle.presentation()
        assert presentation.width == 10
        assert presentation.font_size == 14

    def test_color_schemes(self):
        """Test color scheme definitions."""
        from src.output.exporters.plot_generator import ColorScheme, COLOR_PALETTES

        assert len(COLOR_PALETTES[ColorScheme.IEEE]) == 8
        assert len(COLOR_PALETTES[ColorScheme.ACM]) == 8
        assert len(COLOR_PALETTES[ColorScheme.COLORBLIND_SAFE]) == 7

    def test_plot_data_model(self):
        """Test PlotData model."""
        from src.output.exporters.plot_generator import PlotData

        data = PlotData(
            title="Test Plot",
            xlabel="X Axis",
            ylabel="Y Axis",
            x_data=[1, 2, 3, 4, 5],
            y_data=[10, 20, 15, 25, 30],
            labels=["Series 1"],
        )

        assert data.title == "Test Plot"
        assert len(data.x_data) == 5
        assert len(data.y_data) == 5
        assert data.plot_id is not None


class TestLinePlots:
    """Test line plot generation."""

    def test_simple_line_plot(self):
        """Test simple line plot creation."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Detection Accuracy Over Time",
                xlabel="Epoch",
                ylabel="Accuracy",
                x_data=[1, 2, 3, 4, 5],
                y_data=[0.65, 0.78, 0.85, 0.89, 0.92],
            )

            result = generator.create_line_plot(data, PlotFormat.PNG)

            assert result.success
            assert Path(result.output_path).exists()
            assert result.file_size_bytes > 0
            assert result.base64_data is not None

    def test_multi_series_line_plot(self):
        """Test line plot with multiple series."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Method Comparison",
                xlabel="Epoch",
                ylabel="Loss",
                x_data=[1, 2, 3, 4, 5],
                y_data=[
                    [0.9, 0.7, 0.5, 0.3, 0.2],  # Training
                    [0.95, 0.75, 0.55, 0.35, 0.25],  # Validation
                ],
                labels=["Training Loss", "Validation Loss"],
            )

            result = generator.create_line_plot(data, PlotFormat.PDF)

            assert result.success
            assert result.format == PlotFormat.PDF


class TestBarPlots:
    """Test bar plot generation."""

    def test_simple_bar_plot(self):
        """Test simple bar chart creation."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Detection Results by Category",
                xlabel="Category",
                ylabel="Count",
                x_data=["Normal", "Attack", "Anomaly"],
                y_data=[100, 25, 15],
            )

            result = generator.create_bar_plot(data, PlotFormat.PNG)

            assert result.success
            assert Path(result.output_path).exists()

    def test_grouped_bar_plot(self):
        """Test grouped bar chart."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Method Comparison",
                xlabel="Dataset",
                ylabel="F1 Score",
                x_data=["Dataset A", "Dataset B", "Dataset C"],
                y_data=[
                    [0.85, 0.88, 0.82],  # Method 1
                    [0.91, 0.93, 0.89],  # Method 2
                ],
                labels=["Baseline", "S5-HES"],
            )

            result = generator.create_bar_plot(data, PlotFormat.PDF, grouped=True)

            assert result.success

    def test_horizontal_bar_plot(self):
        """Test horizontal bar chart."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Feature Importance",
                xlabel="Importance",
                ylabel="Feature",
                x_data=["Feature A", "Feature B", "Feature C"],
                y_data=[0.45, 0.32, 0.23],
            )

            result = generator.create_bar_plot(data, PlotFormat.PNG, horizontal=True)

            assert result.success


class TestScatterPlots:
    """Test scatter plot generation."""

    def test_simple_scatter_plot(self):
        """Test simple scatter plot creation."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Precision vs Recall",
                xlabel="Recall",
                ylabel="Precision",
                x_data=[0.7, 0.75, 0.8, 0.85, 0.9, 0.95],
                y_data=[0.95, 0.93, 0.90, 0.85, 0.78, 0.70],
            )

            result = generator.create_scatter_plot(data, PlotFormat.PNG)

            assert result.success


class TestHeatmaps:
    """Test heatmap and confusion matrix generation."""

    def test_heatmap(self):
        """Test heatmap creation."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Correlation Matrix",
                xlabel="Feature",
                ylabel="Feature",
                matrix_data=[
                    [1.0, 0.8, 0.2],
                    [0.8, 1.0, 0.5],
                    [0.2, 0.5, 1.0],
                ],
                row_labels=["A", "B", "C"],
                col_labels=["A", "B", "C"],
            )

            result = generator.create_heatmap(data, PlotFormat.PNG)

            assert result.success

    def test_confusion_matrix(self):
        """Test confusion matrix plot."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Classification Results",
                xlabel="Predicted",
                ylabel="Actual",
                matrix_data=[
                    [85, 10, 5],
                    [8, 82, 10],
                    [3, 7, 90],
                ],
                row_labels=["Normal", "Attack", "Anomaly"],
                col_labels=["Normal", "Attack", "Anomaly"],
            )

            result = generator.create_confusion_matrix(data, PlotFormat.PDF)

            assert result.success


class TestBoxPlots:
    """Test box plot generation."""

    def test_box_plot(self):
        """Test box plot creation."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            # Simulated distribution data
            data = PlotData(
                title="Latency Distribution",
                xlabel="Method",
                ylabel="Latency (ms)",
                x_data=["Method A", "Method B", "Method C"],
                y_data=[
                    [10, 12, 11, 15, 9, 14, 13],  # Method A
                    [20, 22, 18, 25, 21, 19, 23],  # Method B
                    [5, 6, 4, 7, 5, 6, 8],  # Method C
                ],
            )

            result = generator.create_box_plot(data, PlotFormat.PNG)

            assert result.success


class TestHistograms:
    """Test histogram generation."""

    def test_histogram(self):
        """Test histogram creation."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            # Simulated data distribution
            import random
            random.seed(42)
            values = [random.gauss(50, 10) for _ in range(100)]

            data = PlotData(
                title="Score Distribution",
                xlabel="Score",
                ylabel="Frequency",
                y_data=values,
            )

            result = generator.create_histogram(data, PlotFormat.PNG, bins=15)

            assert result.success


class TestConveniencePlotFunctions:
    """Test convenience plot functions."""

    def test_create_comparison_plot(self):
        """Test comparison plot helper."""
        from src.output.exporters.plot_generator import (
            create_comparison_plot,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        result = create_comparison_plot(
            methods=["Baseline", "S5-HES", "Deep Learning"],
            metrics={
                "Accuracy": [0.85, 0.92, 0.95],
                "F1 Score": [0.82, 0.90, 0.93],
            },
            title="Model Comparison",
            format=PlotFormat.PNG,
        )

        assert result.success
        # Clean up
        Path(result.output_path).unlink(missing_ok=True)

    def test_create_training_curve(self):
        """Test training curve helper."""
        from src.output.exporters.plot_generator import (
            create_training_curve,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        result = create_training_curve(
            epochs=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            train_loss=[0.9, 0.7, 0.5, 0.4, 0.3, 0.25, 0.2, 0.18, 0.15, 0.12],
            val_loss=[0.95, 0.75, 0.55, 0.45, 0.35, 0.30, 0.28, 0.27, 0.26, 0.25],
            title="Training Progress",
            format=PlotFormat.PNG,
        )

        assert result.success
        Path(result.output_path).unlink(missing_ok=True)


class TestPlotStatistics:
    """Test plot statistics and history."""

    def test_plot_history(self):
        """Test plot history tracking."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Test",
                x_data=[1, 2, 3],
                y_data=[1, 2, 3],
            )

            generator.create_line_plot(data, PlotFormat.PNG)
            generator.create_bar_plot(data, PlotFormat.PNG)

            history = generator.get_plot_history()
            assert len(history) == 2

    def test_plot_stats(self):
        """Test plot statistics."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Test",
                x_data=[1, 2, 3],
                y_data=[1, 2, 3],
            )

            generator.create_line_plot(data, PlotFormat.PNG)
            generator.create_line_plot(data, PlotFormat.PDF)

            stats = generator.get_stats()

            assert stats["total_plots"] == 2
            assert stats["total_size_bytes"] > 0
            assert "png" in stats["format_breakdown"]
            assert "pdf" in stats["format_breakdown"]


class TestPlotFormatOutput:
    """Test different output formats."""

    def test_svg_output(self):
        """Test SVG output format."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="Vector Plot",
                x_data=[1, 2, 3],
                y_data=[1, 4, 9],
            )

            result = generator.create_line_plot(data, PlotFormat.SVG)

            assert result.success
            assert result.output_path.endswith(".svg")
            assert Path(result.output_path).exists()

    def test_eps_output(self):
        """Test EPS output format."""
        from src.output.exporters.plot_generator import (
            PlotGenerator,
            PlotData,
            PlotFormat,
            is_plotting_available,
        )

        if not is_plotting_available():
            pytest.skip("matplotlib not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlotGenerator(output_dir=tmpdir)

            data = PlotData(
                title="EPS Plot",
                x_data=[1, 2, 3],
                y_data=[1, 4, 9],
            )

            result = generator.create_line_plot(data, PlotFormat.EPS)

            assert result.success
            assert result.output_path.endswith(".eps")


class TestPlotAvailability:
    """Test plotting availability checks."""

    def test_is_plotting_available(self):
        """Test plotting availability check."""
        from src.output.exporters.plot_generator import is_plotting_available

        # Should return True or False without error
        result = is_plotting_available()
        assert isinstance(result, bool)

    def test_get_missing_dependencies(self):
        """Test missing dependencies check."""
        from src.output.exporters.plot_generator import get_missing_dependencies

        missing = get_missing_dependencies()
        assert isinstance(missing, list)


# =============================================================================
# Jupyter Integration Tests (S15.7)
# =============================================================================


class TestJupyterIntegrationCore:
    """Test JupyterIntegration core functionality."""

    def test_jupyter_integration_initialization(self):
        """Test JupyterIntegration initializes correctly."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)
            assert jupyter is not None
            assert jupyter.output_dir.exists()

    def test_data_access_result_model(self):
        """Test DataAccessResult model."""
        from src.output.exporters.jupyter_integration import DataAccessResult

        result = DataAccessResult(
            success=True,
            data={"test": "data"},
            row_count=10,
            column_count=5,
            columns=["a", "b", "c", "d", "e"],
        )

        assert result.success is True
        assert result.row_count == 10
        assert len(result.columns) == 5

    def test_notebook_cell_model(self):
        """Test NotebookCell model."""
        from src.output.exporters.jupyter_integration import NotebookCell

        cell = NotebookCell(
            cell_type="code",
            source="print('hello')",
        )

        assert cell.cell_type == "code"
        assert cell.source == "print('hello')"


class TestDataAccess:
    """Test data access functionality (S15.9)."""

    def test_load_json_file(self):
        """Test loading JSON simulation results."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test JSON file
            test_data = [
                {"id": 1, "value": 10.5, "label": "normal"},
                {"id": 2, "value": 20.3, "label": "attack"},
                {"id": 3, "value": 15.8, "label": "normal"},
            ]
            json_path = Path(tmpdir) / "test_data.json"
            with open(json_path, 'w') as f:
                json.dump(test_data, f)

            jupyter = JupyterIntegration(output_dir=tmpdir)
            result = jupyter.load_simulation_results(filepath=str(json_path))

            assert result.success is True
            assert result.row_count == 3
            assert result.column_count == 3
            assert "id" in result.columns
            assert "value" in result.columns
            assert "label" in result.columns

    def test_load_csv_file(self):
        """Test loading CSV file."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test CSV file
            csv_content = "id,value,label\n1,10.5,normal\n2,20.3,attack\n"
            csv_path = Path(tmpdir) / "test_data.csv"
            csv_path.write_text(csv_content)

            jupyter = JupyterIntegration(output_dir=tmpdir)
            result = jupyter.load_simulation_results(filepath=str(csv_path))

            assert result.success is True
            assert "csv_content" in result.data
            assert result.metadata["format"] == "csv"

    def test_load_nonexistent_file(self):
        """Test handling of non-existent file."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)
            result = jupyter.load_simulation_results(filepath="/nonexistent/path.json")

            assert result.success is False
            assert "not found" in result.error.lower()

    def test_load_by_experiment_id(self):
        """Test loading by experiment ID."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)
            result = jupyter.load_simulation_results(experiment_id="test-exp-123")

            assert result.success is True
            assert result.metadata["experiment_id"] == "test-exp-123"

    def test_get_device_data(self):
        """Test device data retrieval."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)
            result = jupyter.get_device_data(
                home_id="home-123",
                device_type="smart_lock",
            )

            assert result.success is True
            assert result.data["home_id"] == "home-123"
            assert result.data["device_type"] == "smart_lock"

    def test_get_threat_events(self):
        """Test threat events retrieval."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)
            result = jupyter.get_threat_events(
                simulation_id="sim-456",
                threat_type="ddos",
                include_labels=True,
            )

            assert result.success is True
            assert result.metadata["has_ground_truth"] is True

    def test_get_network_traffic(self):
        """Test network traffic retrieval."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)
            result = jupyter.get_network_traffic(
                simulation_id="sim-789",
                protocol="mqtt",
            )

            assert result.success is True
            assert result.metadata["protocol"] == "mqtt"


class TestNotebookGeneration:
    """Test notebook generation functionality."""

    def test_generate_analysis_notebook(self):
        """Test analysis notebook generation."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)
            notebook_path = jupyter.generate_analysis_notebook(
                experiment_id="exp-001",
                include_sections=["setup", "data_loading"],
            )

            assert Path(notebook_path).exists()
            assert notebook_path.endswith(".ipynb")

            # Verify notebook structure
            with open(notebook_path, 'r') as f:
                notebook = json.load(f)

            assert notebook["nbformat"] == 4
            assert len(notebook["cells"]) > 0
            assert notebook["metadata"]["s5hes"]["experiment_id"] == "exp-001"

    def test_generate_analysis_notebook_all_sections(self):
        """Test analysis notebook with all sections."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)
            notebook_path = jupyter.generate_analysis_notebook(
                experiment_id="exp-002",
            )

            with open(notebook_path, 'r') as f:
                notebook = json.load(f)

            # Should have multiple cells for all sections
            assert len(notebook["cells"]) >= 7

    def test_generate_comparison_notebook(self):
        """Test comparison notebook generation."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)
            notebook_path = jupyter.generate_comparison_notebook(
                experiment_ids=["exp-001", "exp-002", "exp-003"],
                comparison_metrics=["accuracy", "f1_score"],
            )

            assert Path(notebook_path).exists()

            with open(notebook_path, 'r') as f:
                notebook = json.load(f)

            assert len(notebook["cells"]) >= 3


class TestDisplayHelpers:
    """Test display helper functions."""

    def test_display_dataframe_list(self):
        """Test displaying list data as HTML table."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)

            data = [
                {"name": "Device A", "value": 10},
                {"name": "Device B", "value": 20},
            ]

            html = jupyter.display_dataframe(data, title="Test Table")

            assert "<table" in html
            assert "Test Table" in html
            assert "Device A" in html
            assert "Device B" in html

    def test_display_dataframe_dict(self):
        """Test displaying dict data."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)

            data = {"data": [{"a": 1}, {"a": 2}]}
            html = jupyter.display_dataframe(data)

            assert "<table" in html

    def test_display_dataframe_max_rows(self):
        """Test max rows limiting."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)

            data = [{"id": i} for i in range(100)]
            html = jupyter.display_dataframe(data, max_rows=5)

            assert "Showing 5 of 100 rows" in html

    def test_display_summary_stats(self):
        """Test summary statistics display."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)

            data = [
                {"value": 10, "score": 0.8},
                {"value": 20, "score": 0.9},
                {"value": 15, "score": 0.85},
            ]

            html = jupyter.display_summary_stats(data)

            assert "count" in html
            assert "mean" in html
            assert "min" in html
            assert "max" in html


class TestCodeSnippets:
    """Test code snippet generation."""

    def test_load_data_snippet(self):
        """Test load data code snippet."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)

            snippet = jupyter.get_code_snippet(
                "load_data",
                filepath="test.json",
            )

            assert "load_simulation_results" in snippet
            assert "test.json" in snippet

    def test_create_plot_snippet(self):
        """Test create plot code snippet."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)

            snippet = jupyter.get_code_snippet(
                "create_plot",
                title="Test Plot",
                xlabel="X",
                ylabel="Y",
                x_data=[1, 2, 3],
                y_data=[1, 4, 9],
            )

            assert "PlotGenerator" in snippet
            assert "Test Plot" in snippet

    def test_unknown_snippet(self):
        """Test handling unknown snippet type."""
        from src.output.exporters.jupyter_integration import JupyterIntegration

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = JupyterIntegration(output_dir=tmpdir)

            snippet = jupyter.get_code_snippet("unknown_operation")

            assert "Unknown operation" in snippet


class TestJupyterSingletonAndFactories:
    """Test singleton and factory functions."""

    def test_get_jupyter_integration(self):
        """Test getting singleton instance."""
        from src.output.exporters.jupyter_integration import (
            get_jupyter_integration,
        )
        import src.output.exporters.jupyter_integration as module

        # Reset singleton
        module._jupyter_instance = None

        jupyter1 = get_jupyter_integration()
        jupyter2 = get_jupyter_integration()

        assert jupyter1 is jupyter2

    def test_initialize_jupyter_integration(self):
        """Test initializing with custom config."""
        from src.output.exporters.jupyter_integration import (
            initialize_jupyter_integration,
        )
        import src.output.exporters.jupyter_integration as module

        # Reset singleton
        module._jupyter_instance = None

        with tempfile.TemporaryDirectory() as tmpdir:
            jupyter = initialize_jupyter_integration(
                api_base_url="http://custom:9000/api",
                output_dir=tmpdir,
            )

            assert jupyter.api_base_url == "http://custom:9000/api"
            assert str(jupyter.output_dir) == tmpdir


# =============================================================================
# Export Wizard Tests (S15.11-12)
# =============================================================================


class TestExportWizardCore:
    """Test ExportWizard core functionality."""

    def test_wizard_initialization(self):
        """Test ExportWizard initializes correctly."""
        from src.output.exporters.export_wizard import ExportWizard

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            assert wizard is not None
            assert wizard.output_dir.exists()

    def test_start_wizard(self):
        """Test starting a wizard session."""
        from src.output.exporters.export_wizard import ExportWizard, WizardStep

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            state = wizard.start_wizard()

            assert state is not None
            assert state.current_step == WizardStep.FORMAT_SELECTION
            assert state.wizard_id is not None

    def test_start_wizard_with_template(self):
        """Test starting wizard with a template."""
        from src.output.exporters.export_wizard import (
            ExportWizard,
            ExportTemplate,
        )
        from src.output.exporters.publication_exporter import PublicationFormat

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            state = wizard.start_wizard(template=ExportTemplate.IEEE_JOURNAL)

            assert state.template == ExportTemplate.IEEE_JOURNAL
            assert state.publication_format == PublicationFormat.IEEE

    def test_wizard_state_model(self):
        """Test WizardState model."""
        from src.output.exporters.export_wizard import WizardState, WizardStep

        state = WizardState()

        assert state.wizard_id is not None
        assert state.current_step == WizardStep.FORMAT_SELECTION
        assert state.include_tables is True
        assert len(state.tables) == 0


class TestWizardNavigation:
    """Test wizard step navigation."""

    def test_next_step(self):
        """Test moving to next step."""
        from src.output.exporters.export_wizard import ExportWizard, WizardStep

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            wizard.start_wizard()

            next_step = wizard.next_step()
            assert next_step == WizardStep.CONTENT_SELECTION

            next_step = wizard.next_step()
            assert next_step == WizardStep.STYLE_CONFIGURATION

    def test_previous_step(self):
        """Test moving to previous step."""
        from src.output.exporters.export_wizard import ExportWizard, WizardStep

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            wizard.start_wizard()

            wizard.next_step()  # Move to CONTENT_SELECTION
            wizard.next_step()  # Move to STYLE_CONFIGURATION

            prev_step = wizard.previous_step()
            assert prev_step == WizardStep.CONTENT_SELECTION

    def test_go_to_step(self):
        """Test jumping to specific step."""
        from src.output.exporters.export_wizard import ExportWizard, WizardStep

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            wizard.start_wizard()

            step = wizard.go_to_step(WizardStep.PREVIEW)
            assert step == WizardStep.PREVIEW


class TestWizardConfiguration:
    """Test wizard configuration methods."""

    def test_set_format(self):
        """Test setting publication format."""
        from src.output.exporters.export_wizard import ExportWizard
        from src.output.exporters.publication_exporter import (
            PublicationFormat,
            ExportFormat,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            wizard.start_wizard()

            state = wizard.set_format(
                PublicationFormat.ACM,
                ExportFormat.LATEX,
            )

            assert state.publication_format == PublicationFormat.ACM
            assert state.export_format == ExportFormat.LATEX

    def test_set_content_options(self):
        """Test setting content options."""
        from src.output.exporters.export_wizard import ExportWizard

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            wizard.start_wizard()

            state = wizard.set_content_options(
                include_tables=True,
                include_figures=False,
                include_methodology=True,
            )

            assert state.include_tables is True
            assert state.include_figures is False
            assert state.include_methodology is True

    def test_set_metadata(self):
        """Test setting metadata."""
        from src.output.exporters.export_wizard import ExportWizard

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            wizard.start_wizard()

            state = wizard.set_metadata(
                title="Test Publication",
                authors=["Author 1", "Author 2"],
                keywords=["IoT", "Security"],
            )

            assert state.title == "Test Publication"
            assert len(state.authors) == 2
            assert "IoT" in state.keywords

    def test_add_table(self):
        """Test adding a table."""
        from src.output.exporters.export_wizard import ExportWizard
        from src.output.exporters.publication_exporter import TableData, TableColumn

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            wizard.start_wizard()

            table = TableData(
                title="Results",
                caption="Test results",
                label="tab:results",
                columns=[TableColumn(name="x", header="X")],
                rows=[{"x": 1}],
            )

            state = wizard.add_table(table)
            assert len(state.tables) == 1


class TestWizardValidation:
    """Test wizard validation functionality."""

    def test_validate_empty_config(self):
        """Test validation with empty configuration."""
        from src.output.exporters.export_wizard import ExportWizard

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            wizard.start_wizard()

            result = wizard.validate()

            assert result.valid is False
            assert len(result.errors) > 0  # Missing format

    def test_validate_complete_config(self):
        """Test validation with complete configuration."""
        from src.output.exporters.export_wizard import ExportWizard
        from src.output.exporters.publication_exporter import (
            PublicationFormat,
            ExportFormat,
            TableData,
            TableColumn,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            wizard.start_wizard()

            wizard.set_format(PublicationFormat.IEEE, ExportFormat.LATEX)
            wizard.set_metadata(
                title="Test",
                authors=["Author"],
            )
            wizard.add_table(TableData(
                title="T",
                caption="C",
                label="L",
                columns=[TableColumn(name="x", header="X")],
                rows=[{"x": 1}],
            ))

            result = wizard.validate()

            assert result.valid is True
            assert len(result.errors) == 0


class TestWizardTemplates:
    """Test wizard template functionality."""

    def test_get_available_templates(self):
        """Test getting available templates."""
        from src.output.exporters.export_wizard import ExportWizard

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            templates = wizard.get_available_templates()

            assert len(templates) >= 6
            names = [t.name for t in templates]
            assert "IEEE Journal" in names
            assert "ACM Journal" in names

    def test_get_template_config(self):
        """Test getting specific template config."""
        from src.output.exporters.export_wizard import ExportWizard, ExportTemplate

        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = ExportWizard(output_dir=tmpdir)
            config = wizard.get_template_config(ExportTemplate.IEEE_JOURNAL)

            assert config is not None
            assert config.name == "IEEE Journal"
            assert config.figure_dpi == 300


class TestPublicationPreview:
    """Test publication preview functionality."""

    def test_preview_initialization(self):
        """Test PublicationPreview initializes correctly."""
        from src.output.exporters.export_wizard import PublicationPreview

        preview = PublicationPreview()
        assert preview is not None

    def test_generate_html_preview(self):
        """Test HTML preview generation."""
        from src.output.exporters.export_wizard import (
            PublicationPreview,
            WizardState,
            PreviewFormat,
        )
        from src.output.exporters.publication_exporter import (
            PublicationFormat,
            ExportFormat,
        )

        preview = PublicationPreview()

        state = WizardState(
            title="Test Publication",
            authors=["Author One", "Author Two"],
            abstract="This is a test abstract.",
            keywords=["test", "preview"],
            publication_format=PublicationFormat.IEEE,
            export_format=ExportFormat.LATEX,
        )

        result = preview.generate_preview(state, PreviewFormat.HTML)

        assert result.success is True
        assert "Test Publication" in result.content
        assert "Author One" in result.content
        assert result.word_count > 0

    def test_generate_text_preview(self):
        """Test text preview generation."""
        from src.output.exporters.export_wizard import (
            PublicationPreview,
            WizardState,
            PreviewFormat,
        )

        preview = PublicationPreview()

        state = WizardState(
            title="Text Preview Test",
            authors=["Test Author"],
        )

        result = preview.generate_preview(state, PreviewFormat.TEXT)

        assert result.success is True
        assert "Text Preview Test" in result.content

    def test_generate_json_preview(self):
        """Test JSON preview generation."""
        from src.output.exporters.export_wizard import (
            PublicationPreview,
            WizardState,
            PreviewFormat,
        )

        preview = PublicationPreview()
        state = WizardState(title="JSON Test")

        result = preview.generate_preview(state, PreviewFormat.JSON)

        assert result.success is True
        assert "JSON Test" in result.content

        # Should be valid JSON
        parsed = json.loads(result.content)
        assert parsed["title"] == "JSON Test"

    def test_generate_latex_snippet(self):
        """Test LaTeX snippet generation."""
        from src.output.exporters.export_wizard import (
            PublicationPreview,
            WizardState,
        )
        from src.output.exporters.publication_exporter import PublicationFormat

        preview = PublicationPreview()

        state = WizardState(
            title="LaTeX Test",
            authors=["Author A", "Author B"],
            abstract="Test abstract content.",
            publication_format=PublicationFormat.IEEE,
        )

        latex = preview.generate_latex_snippet(state)

        assert r"\documentclass{article}" in latex
        assert r"\title{LaTeX Test}" in latex
        assert r"\author{" in latex
        assert r"\begin{abstract}" in latex


class TestPreviewWithContent:
    """Test preview with various content types."""

    def test_preview_with_tables(self):
        """Test preview with tables."""
        from src.output.exporters.export_wizard import (
            PublicationPreview,
            WizardState,
            PreviewFormat,
        )
        from src.output.exporters.publication_exporter import TableData, TableColumn

        preview = PublicationPreview()

        state = WizardState(
            title="Table Test",
            include_tables=True,
            tables=[
                TableData(
                    title="Results",
                    caption="Test results table",
                    label="tab:results",
                    columns=[
                        TableColumn(name="method", header="Method"),
                        TableColumn(name="score", header="Score", format_spec=".2f"),
                    ],
                    rows=[
                        {"method": "A", "score": 0.95},
                        {"method": "B", "score": 0.87},
                    ],
                )
            ],
        )

        result = preview.generate_preview(state, PreviewFormat.HTML)

        assert "Table 1:" in result.content
        assert "Test results table" in result.content
        assert "Method" in result.content

    def test_preview_with_citations(self):
        """Test preview with citations."""
        from src.output.exporters.export_wizard import (
            PublicationPreview,
            WizardState,
            PreviewFormat,
        )
        from src.output.exporters.publication_exporter import Citation

        preview = PublicationPreview()

        state = WizardState(
            title="Citation Test",
            include_citations=True,
            citations=[
                Citation(
                    cite_key="smith2023",
                    entry_type="article",
                    title="Test Paper",
                    author="Smith, John",
                    year=2023,
                ),
            ],
        )

        result = preview.generate_preview(state, PreviewFormat.HTML)

        assert "References" in result.content
        assert "Smith, John" in result.content
        assert "Test Paper" in result.content


class TestExportWizardSingletons:
    """Test singleton and factory functions."""

    def test_get_export_wizard(self):
        """Test getting singleton wizard."""
        from src.output.exporters.export_wizard import get_export_wizard
        import src.output.exporters.export_wizard as module

        # Reset singleton
        module._wizard_instance = None

        wizard1 = get_export_wizard()
        wizard2 = get_export_wizard()

        assert wizard1 is wizard2

    def test_get_publication_preview(self):
        """Test getting singleton preview."""
        from src.output.exporters.export_wizard import get_publication_preview
        import src.output.exporters.export_wizard as module

        # Reset singleton
        module._preview_instance = None

        preview1 = get_publication_preview()
        preview2 = get_publication_preview()

        assert preview1 is preview2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
