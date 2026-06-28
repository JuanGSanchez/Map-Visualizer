"""
Tests for map_visualizer.core — the headless render core.

Coverage targets
----------------
* load_array: happy paths, 1-D promotion, typed exception paths (R-2/R-3)
* array_stats: correctness on clean + partial-NaN grids
* render: all four modes, PNG-magic assertion, parameter variations, error paths
* list_colormaps / list_interpolations: non-empty, contain expected entries
* draw_* Axes helpers: exercise each without pyplot
* apply_value_range: clamp behaviour
* _sci_exp_for_range: edge-case coverage (zero ref, in-range, large)
"""
from __future__ import annotations

import io
import math
import os
import textwrap

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pytest

from map_visualizer import (
    GridLoadError,
    GridValidationError,
    InvalidParameterError,
    RenderError,
    RenderMode,
    array_stats,
    apply_value_range,
    downsample,
    draw_contour,
    draw_heatmap,
    draw_histogram,
    draw_profile,
    list_colormaps,
    list_interpolations,
    load_array,
    render,
)

# PNG magic bytes (first 8 bytes of every valid PNG file)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# ===========================================================================
# list_colormaps / list_interpolations
# ===========================================================================

class TestListColormaps:
    def test_returns_nonempty_list(self):
        cmaps = list_colormaps()
        assert isinstance(cmaps, list)
        assert len(cmaps) > 0

    def test_contains_viridis(self):
        assert "viridis" in list_colormaps()

    def test_contains_plasma(self):
        assert "plasma" in list_colormaps()

    def test_contains_inferno(self):
        assert "inferno" in list_colormaps()

    def test_all_strings(self):
        for name in list_colormaps():
            assert isinstance(name, str)

    def test_sorted(self):
        cmaps = list_colormaps()
        assert cmaps == sorted(cmaps)

    def test_returns_copy(self):
        # Mutating the return value must not corrupt the cache.
        c1 = list_colormaps()
        c1.clear()
        c2 = list_colormaps()
        assert len(c2) > 0


class TestListInterpolations:
    def test_returns_nonempty_list(self):
        interps = list_interpolations()
        assert isinstance(interps, list)
        assert len(interps) > 0

    def test_contains_nearest(self):
        assert "nearest" in list_interpolations()

    def test_contains_bilinear(self):
        assert "bilinear" in list_interpolations()

    def test_all_strings(self):
        for name in list_interpolations():
            assert isinstance(name, str)

    def test_sorted(self):
        interps = list_interpolations()
        assert interps == sorted(interps)


# ===========================================================================
# load_array — happy paths
# ===========================================================================

class TestLoadArrayHappy:
    def test_from_txt_file(self, grid_txt_file, simple_3x3):
        arr = load_array(grid_txt_file)
        assert arr.ndim == 2
        assert arr.shape == (3, 3)
        np.testing.assert_allclose(arr, simple_3x3)

    def test_from_dat_file(self, grid_dat_file, simple_5x4):
        arr = load_array(grid_dat_file)
        assert arr.ndim == 2
        assert arr.shape == (5, 4)

    def test_from_inline_text(self, inline_text_3x3):
        arr = load_array(inline_text_3x3)
        assert arr.ndim == 2
        assert arr.shape == (3, 3)

    def test_result_is_float64(self, simple_3x3, grid_txt_file):
        arr = load_array(grid_txt_file)
        assert arr.dtype == np.float64

    def test_returns_2d(self, inline_text_3x3):
        arr = load_array(inline_text_3x3)
        assert arr.ndim == 2

    def test_from_file_like_stringio(self):
        text = "10.0 20.0\n30.0 40.0\n"
        arr = load_array(io.StringIO(text))
        assert arr.shape == (2, 2)
        assert arr[0, 0] == pytest.approx(10.0)
        assert arr[1, 1] == pytest.approx(40.0)

    def test_from_file_like_bytesio(self, tmp_path):
        # BytesIO contains UTF-8 encoded whitespace text.
        text = b"5.0 6.0\n7.0 8.0\n"
        arr = load_array(io.BytesIO(text))
        assert arr.shape == (2, 2)

    def test_1d_single_row_promoted(self, tmp_path):
        # A file with a single row is promoted to (1, N).
        p = tmp_path / "row.txt"
        p.write_text("1.0 2.0 3.0 4.0\n")
        arr = load_array(str(p))
        assert arr.ndim == 2
        assert arr.shape == (1, 4)

    def test_1d_single_column_promoted(self, tmp_path):
        # A file with N rows each of 1 number — np.loadtxt returns 1-D,
        # so load_array promotes it to (1, N).
        p = tmp_path / "col.txt"
        p.write_text("1.0\n2.0\n3.0\n")
        arr = load_array(str(p))
        assert arr.ndim == 2
        # Promoted to (1, 3) because a 1-D array of length 3 becomes (1, 3).
        assert arr.shape == (1, 3)

    def test_max_cells_custom(self):
        # A small grid with a generous cap passes fine.
        arr = load_array("1.0 2.0\n3.0 4.0", max_cells=100)
        assert arr.shape == (2, 2)

    def test_max_cells_zero_disables_cap(self, tmp_path):
        # max_cells=0 → no limit.
        data = " ".join(str(float(i)) for i in range(100))
        p = tmp_path / "big.txt"
        p.write_text(data + "\n")
        arr = load_array(str(p), max_cells=0)
        assert arr.shape == (1, 100)

    def test_partial_nan_loads_ok(self, grid_with_nan_file):
        # Arrays with some (not all) NaN cells must load without error.
        arr = load_array(grid_with_nan_file)
        assert arr.ndim == 2
        assert np.any(np.isnan(arr))

    def test_pathlike_object(self, tmp_path):
        import pathlib
        p = tmp_path / "pathlike.txt"
        p.write_text("1.0 2.0\n3.0 4.0\n")
        arr = load_array(p)
        assert arr.shape == (2, 2)


# ===========================================================================
# load_array — hardened error paths (R-2 / R-3)
# ===========================================================================

class TestLoadArrayErrors:
    def test_missing_file_raises_grid_load_error(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.txt")
        with pytest.raises(GridLoadError):
            load_array(missing)

    def test_bad_extension_raises_grid_load_error(self, tmp_path):
        # .csv is now supported (SPEC-15); use a genuinely unsupported ext.
        p = tmp_path / "grid.json"
        p.write_text("1,2\n3,4\n")
        with pytest.raises(GridLoadError):
            load_array(str(p))

    def test_ragged_rows_raises_grid_validation_error(self):
        # Different column counts per row — ragged grid.
        ragged = "1.0 2.0 3.0\n4.0 5.0\n"
        with pytest.raises(GridValidationError):
            load_array(ragged)

    def test_empty_input_raises_grid_validation_error(self, tmp_path):
        # An empty file produces a zero-element array.
        p = tmp_path / "empty.txt"
        p.write_text("")
        with pytest.raises(GridValidationError):
            load_array(str(p))

    def test_all_nan_raises_grid_validation_error(self):
        # A string full of NaN values must raise GridValidationError.
        nan_text = "nan nan\nnan nan\n"
        with pytest.raises(GridValidationError):
            load_array(nan_text)

    def test_oversize_raises_grid_validation_error(self):
        # Grid exceeds the supplied max_cells.
        text = "1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0\n"  # 9 cells
        with pytest.raises(GridValidationError):
            load_array(text, max_cells=5)

    def test_non_numeric_raises_grid_load_error(self, tmp_path):
        p = tmp_path / "text.txt"
        p.write_text("alpha beta\ngamma delta\n")
        with pytest.raises(GridLoadError):
            load_array(str(p))

    def test_empty_inline_string_raises_grid_validation_error(self):
        # An empty/whitespace-only multi-line string (no newline → path heuristic
        # routes to path; but an inline-routed empty body should raise).
        with pytest.raises((GridLoadError, GridValidationError)):
            load_array("\n\n")

    def test_ragged_error_is_typed_not_bare(self):
        # Ensure the exception type is specifically GridValidationError,
        # not a bare Exception or a generic MapVisualizerError.
        ragged = "1.0 2.0\n3.0\n"
        exc = None
        try:
            load_array(ragged)
        except GridValidationError as e:
            exc = e
        assert exc is not None, "Expected GridValidationError, nothing raised"

    def test_all_nan_error_is_typed(self):
        nan_text = "nan\nnan\n"
        exc = None
        try:
            load_array(nan_text)
        except GridValidationError as e:
            exc = e
        assert exc is not None, "Expected GridValidationError, nothing raised"


# ===========================================================================
# array_stats
# ===========================================================================

class TestArrayStats:
    def test_shape_key(self, simple_3x3):
        stats = array_stats(simple_3x3)
        assert stats["shape"] == (3, 3)

    def test_min_max(self, simple_3x3):
        stats = array_stats(simple_3x3)
        assert stats["min"] == pytest.approx(1.0)
        assert stats["max"] == pytest.approx(9.0)

    def test_nanmin_nanmax(self, simple_3x3):
        stats = array_stats(simple_3x3)
        assert stats["nanmin"] == pytest.approx(1.0)
        assert stats["nanmax"] == pytest.approx(9.0)

    def test_mean(self, simple_3x3):
        stats = array_stats(simple_3x3)
        assert stats["mean"] == pytest.approx(5.0)

    def test_std(self, simple_3x3):
        stats = array_stats(simple_3x3)
        expected_std = float(np.nanstd(simple_3x3))
        assert stats["std"] == pytest.approx(expected_std)

    def test_nan_count_zero_for_clean_grid(self, simple_3x3):
        stats = array_stats(simple_3x3)
        assert stats["nan_count"] == 0

    def test_nan_count_partial(self, array_with_nans):
        stats = array_stats(array_with_nans)
        assert stats["nan_count"] == 1

    def test_nanmin_nanmax_ignores_nan(self, array_with_nans):
        # With centre cell NaN, nanmin/nanmax must still use the finite cells.
        stats = array_stats(array_with_nans)
        assert stats["nanmin"] == pytest.approx(1.0)
        assert stats["nanmax"] == pytest.approx(9.0)

    def test_mean_ignores_nan(self, array_with_nans):
        # Mean should be computed over the 8 finite cells.
        finite = np.array([1, 2, 3, 4, 6, 7, 8, 9], dtype=float)
        stats = array_stats(array_with_nans)
        assert stats["mean"] == pytest.approx(np.mean(finite))

    def test_sci_exp_key_present(self, simple_3x3):
        stats = array_stats(simple_3x3)
        assert "sci_exp" in stats

    def test_sci_exp_in_range_values(self, simple_3x3):
        # Values 1-9 are in [0.01, 1000) so sci_exp should be 0.
        stats = array_stats(simple_3x3)
        assert stats["sci_exp"] == 0

    def test_sci_exp_large_values(self):
        # Array of 1e6 — outside comfortable range.
        arr = np.full((2, 2), 1e6)
        stats = array_stats(arr)
        assert stats["sci_exp"] != 0

    def test_sci_exp_tiny_values(self):
        arr = np.full((2, 2), 1e-5)
        stats = array_stats(arr)
        assert stats["sci_exp"] != 0

    def test_sci_exp_zero_array(self):
        arr = np.zeros((2, 2))
        stats = array_stats(arr)
        assert stats["sci_exp"] == 0

    def test_return_type_is_dict(self, simple_3x3):
        stats = array_stats(simple_3x3)
        assert isinstance(stats, dict)


# ===========================================================================
# render — PNG magic + all four modes
# ===========================================================================

class TestRenderHeatmap:
    def test_returns_bytes(self, simple_3x3):
        result = render(simple_3x3, mode="heatmap")
        assert isinstance(result, bytes)

    def test_nonempty_bytes(self, simple_3x3):
        result = render(simple_3x3, mode="heatmap")
        assert len(result) > 0

    def test_png_magic(self, simple_3x3):
        result = render(simple_3x3, mode="heatmap")
        assert result[:8] == PNG_MAGIC

    def test_non_default_cmap(self, simple_3x3):
        result = render(simple_3x3, mode="heatmap", cmap="plasma")
        assert result[:8] == PNG_MAGIC

    def test_non_default_interpolation(self, simple_3x3):
        result = render(simple_3x3, mode="heatmap", interpolation="bilinear")
        assert result[:8] == PNG_MAGIC

    def test_value_range_clamping(self, simple_3x3):
        # Providing value_range must not raise and must still return PNG.
        result = render(simple_3x3, mode="heatmap", value_range=(2.0, 8.0))
        assert result[:8] == PNG_MAGIC

    def test_color_range(self, simple_3x3):
        result = render(simple_3x3, mode="heatmap", color_range=(0.0, 10.0))
        assert result[:8] == PNG_MAGIC

    def test_cmap_and_interpolation_combined(self, simple_3x3):
        result = render(simple_3x3, mode="heatmap", cmap="inferno",
                        interpolation="bicubic")
        assert result[:8] == PNG_MAGIC


class TestRenderContour:
    def test_returns_bytes(self, simple_5x4):
        result = render(simple_5x4, mode="contour")
        assert isinstance(result, bytes)

    def test_png_magic(self, simple_5x4):
        result = render(simple_5x4, mode="contour")
        assert result[:8] == PNG_MAGIC

    def test_with_value_range(self, simple_5x4):
        result = render(simple_5x4, mode="contour",
                        value_range=(2.0, 18.0), color_range=(0.0, 20.0))
        assert result[:8] == PNG_MAGIC

    def test_non_default_cmap(self, simple_5x4):
        result = render(simple_5x4, mode="contour", cmap="coolwarm")
        assert result[:8] == PNG_MAGIC


class TestRenderHistogram:
    def test_returns_bytes(self, simple_3x3):
        result = render(simple_3x3, mode="histogram")
        assert isinstance(result, bytes)

    def test_png_magic(self, simple_3x3):
        result = render(simple_3x3, mode="histogram")
        assert result[:8] == PNG_MAGIC

    def test_histogram_with_nans(self, array_with_nans):
        # Partial NaN arrays must still render (NaN cells are skipped).
        result = render(array_with_nans, mode="histogram")
        assert result[:8] == PNG_MAGIC

    def test_non_default_cmap(self, simple_3x3):
        result = render(simple_3x3, mode="histogram", cmap="magma")
        assert result[:8] == PNG_MAGIC


class TestRenderProfile:
    def test_returns_bytes(self, simple_3x3):
        result = render(simple_3x3, mode="profile")
        assert isinstance(result, bytes)

    def test_png_magic(self, simple_3x3):
        result = render(simple_3x3, mode="profile")
        assert result[:8] == PNG_MAGIC

    def test_profile_axis_row(self, simple_3x3):
        result = render(simple_3x3, mode="profile", profile_axis="row")
        assert result[:8] == PNG_MAGIC

    def test_profile_axis_col(self, simple_3x3):
        result = render(simple_3x3, mode="profile", profile_axis="col")
        assert result[:8] == PNG_MAGIC

    def test_explicit_profile_index_row(self, simple_3x3):
        result = render(simple_3x3, mode="profile", profile_axis="row",
                        profile_index=0)
        assert result[:8] == PNG_MAGIC

    def test_explicit_profile_index_col(self, simple_3x3):
        result = render(simple_3x3, mode="profile", profile_axis="col",
                        profile_index=2)
        assert result[:8] == PNG_MAGIC

    def test_profile_default_index(self, simple_5x4):
        # profile_index=None means middle row/col — must work without error.
        result = render(simple_5x4, mode="profile", profile_axis="row",
                        profile_index=None)
        assert result[:8] == PNG_MAGIC


# ===========================================================================
# render — invalid parameter error paths
# ===========================================================================

class TestRenderErrors:
    def test_invalid_mode_raises_invalid_parameter_error(self, simple_3x3):
        with pytest.raises(InvalidParameterError):
            render(simple_3x3, mode="bogus_mode")

    def test_invalid_cmap_raises_invalid_parameter_error(self, simple_3x3):
        with pytest.raises(InvalidParameterError):
            render(simple_3x3, cmap="not_a_real_cmap")

    def test_invalid_interpolation_raises_invalid_parameter_error(self, simple_3x3):
        with pytest.raises(InvalidParameterError):
            render(simple_3x3, interpolation="not_a_real_interp")

    def test_1d_array_raises_render_error(self):
        arr_1d = np.arange(5.0)  # 1-D; render requires 2-D
        with pytest.raises(RenderError):
            render(arr_1d, mode="heatmap")

    def test_profile_invalid_axis_raises_invalid_parameter_error(self, simple_3x3):
        with pytest.raises(InvalidParameterError):
            render(simple_3x3, mode="profile", profile_axis="diagonal")

    def test_profile_out_of_range_index_raises_invalid_parameter_error(
            self, simple_3x3):
        # simple_3x3 has 3 rows (indices 0-2); index 10 is out of range.
        with pytest.raises(InvalidParameterError):
            render(simple_3x3, mode="profile", profile_axis="row",
                   profile_index=10)

    def test_render_mode_enum_heatmap_works(self, simple_3x3):
        # RenderMode enum values must be accepted in place of plain strings.
        result = render(simple_3x3, mode=RenderMode.HEATMAP)
        assert result[:8] == PNG_MAGIC

    def test_render_mode_enum_contour_works(self, simple_5x4):
        result = render(simple_5x4, mode=RenderMode.CONTOUR)
        assert result[:8] == PNG_MAGIC

    def test_render_mode_enum_histogram_works(self, simple_3x3):
        result = render(simple_3x3, mode=RenderMode.HISTOGRAM)
        assert result[:8] == PNG_MAGIC

    def test_render_mode_enum_profile_works(self, simple_3x3):
        result = render(simple_3x3, mode=RenderMode.PROFILE)
        assert result[:8] == PNG_MAGIC


# ===========================================================================
# draw_* Axes-level helpers
# ===========================================================================

class TestDrawHeatmap:
    def test_draws_without_error(self, fig_ax, simple_3x3):
        fig, ax = fig_ax
        draw_heatmap(ax, fig, simple_3x3)
        # Artist count must have grown (imshow + colorbar add artists).
        assert len(ax.get_children()) > 0

    def test_draws_with_cmap_and_interp(self, fig_ax, simple_3x3):
        fig, ax = fig_ax
        draw_heatmap(ax, fig, simple_3x3, cmap="magma",
                     interpolation="bilinear")
        assert len(ax.get_children()) > 0

    def test_draws_with_color_range(self, fig_ax, simple_3x3):
        fig, ax = fig_ax
        draw_heatmap(ax, fig, simple_3x3, color_range=(2.0, 8.0))
        assert len(ax.get_children()) > 0


class TestDrawContour:
    def test_draws_without_error(self, fig_ax, simple_5x4):
        fig, ax = fig_ax
        draw_contour(ax, fig, simple_5x4)
        assert len(ax.get_children()) > 0

    def test_draws_with_color_range(self, fig_ax, simple_5x4):
        fig, ax = fig_ax
        draw_contour(ax, fig, simple_5x4, color_range=(1.0, 20.0))
        assert len(ax.get_children()) > 0


class TestDrawHistogram:
    def test_draws_without_error(self, fig_ax, simple_3x3):
        _, ax = fig_ax
        draw_histogram(ax, simple_3x3)
        assert len(ax.get_children()) > 0

    def test_draws_with_nans(self, fig_ax, array_with_nans):
        _, ax = fig_ax
        draw_histogram(ax, array_with_nans)
        assert len(ax.get_children()) > 0

    def test_draws_with_non_default_cmap(self, fig_ax, simple_3x3):
        _, ax = fig_ax
        draw_histogram(ax, simple_3x3, cmap="plasma")
        assert len(ax.get_children()) > 0


class TestDrawProfile:
    def test_draws_row_without_error(self, fig_ax, simple_3x3):
        _, ax = fig_ax
        draw_profile(ax, simple_3x3, profile_axis="row")
        assert len(ax.get_children()) > 0

    def test_draws_col_without_error(self, fig_ax, simple_3x3):
        _, ax = fig_ax
        draw_profile(ax, simple_3x3, profile_axis="col")
        assert len(ax.get_children()) > 0

    def test_draws_explicit_index_row(self, fig_ax, simple_5x4):
        _, ax = fig_ax
        draw_profile(ax, simple_5x4, profile_axis="row", profile_index=2)
        assert len(ax.get_children()) > 0

    def test_draws_explicit_index_col(self, fig_ax, simple_5x4):
        _, ax = fig_ax
        draw_profile(ax, simple_5x4, profile_axis="col", profile_index=1)
        assert len(ax.get_children()) > 0


# ===========================================================================
# apply_value_range
# ===========================================================================

class TestApplyValueRange:
    def test_clips_below_vmin(self):
        arr = np.array([[0.0, 5.0], [10.0, 15.0]])
        result = apply_value_range(arr, (3.0, 12.0))
        assert result[0, 0] == pytest.approx(3.0)

    def test_clips_above_vmax(self):
        arr = np.array([[0.0, 5.0], [10.0, 15.0]])
        result = apply_value_range(arr, (3.0, 12.0))
        assert result[1, 1] == pytest.approx(12.0)

    def test_preserves_in_range_values(self):
        arr = np.array([[0.0, 5.0], [10.0, 15.0]])
        result = apply_value_range(arr, (3.0, 12.0))
        assert result[0, 1] == pytest.approx(5.0)
        assert result[1, 0] == pytest.approx(10.0)

    def test_preserves_shape(self, simple_3x3):
        result = apply_value_range(simple_3x3, (2.0, 8.0))
        assert result.shape == simple_3x3.shape

    def test_returns_new_array(self, simple_3x3):
        result = apply_value_range(simple_3x3, (2.0, 8.0))
        assert result is not simple_3x3


# ===========================================================================
# RenderMode enum
# ===========================================================================

class TestRenderModeEnum:
    def test_values_are_strings(self):
        for mode in RenderMode:
            assert isinstance(mode.value, str)

    def test_heatmap_value(self):
        assert RenderMode.HEATMAP == "heatmap"

    def test_contour_value(self):
        assert RenderMode.CONTOUR == "contour"

    def test_histogram_value(self):
        assert RenderMode.HISTOGRAM == "histogram"

    def test_profile_value(self):
        assert RenderMode.PROFILE == "profile"

    def test_values_classmethod(self):
        vals = RenderMode.values()
        assert "heatmap" in vals
        assert "contour" in vals
        assert "histogram" in vals
        assert "profile" in vals

    def test_round_trip(self):
        for mode in RenderMode:
            assert RenderMode(mode.value) is mode


# ===========================================================================
# resources.resource_path (smoke test — ensures import + call work)
# ===========================================================================

class TestResourcePath:
    def test_returns_string(self):
        from map_visualizer.resources import resource_path
        result = resource_path("Logo MVis.png")
        assert isinstance(result, str)

    def test_is_absolute_path(self):
        from map_visualizer.resources import resource_path
        result = resource_path("something.txt")
        assert os.path.isabs(result)


# ===========================================================================
# SPEC-14 — extended render modes (contourf, surface3d, profile_row/col)
# ===========================================================================

SVG_MAGIC = b"<?xml"
PDF_MAGIC = b"%PDF"


class TestRenderExtendedModes:
    @pytest.mark.parametrize(
        "mode",
        ["heatmap", "contour", "contourf", "surface3d",
         "histogram", "profile", "profile_row", "profile_col"],
    )
    def test_each_mode_returns_png(self, simple_5x4, mode):
        # SPEC-11: every mode renders a valid PNG headlessly under Agg.
        result = render(simple_5x4, mode=mode)
        assert result[:8] == PNG_MAGIC
        assert len(result) > 0

    def test_contourf_has_no_line_overlay_param(self, simple_5x4):
        # contourf and contour are distinct modes that both render.
        a = render(simple_5x4, mode="contourf")
        b = render(simple_5x4, mode="contour")
        assert a[:8] == PNG_MAGIC and b[:8] == PNG_MAGIC

    def test_surface3d_with_nans(self, array_with_nans):
        # NaNs are filled before plot_surface — must not raise.
        result = render(array_with_nans, mode="surface3d")
        assert result[:8] == PNG_MAGIC

    def test_contour_explicit_levels(self, simple_5x4):
        result = render(simple_5x4, mode="contour", levels=5)
        assert result[:8] == PNG_MAGIC

    def test_contour_invalid_levels_raises(self, simple_5x4):
        with pytest.raises(InvalidParameterError):
            render(simple_5x4, mode="contour", levels=0)

    def test_histogram_explicit_bins(self, simple_5x4):
        result = render(simple_5x4, mode="histogram", bins=10)
        assert result[:8] == PNG_MAGIC

    def test_histogram_invalid_bins_raises(self, simple_5x4):
        with pytest.raises(InvalidParameterError):
            render(simple_5x4, mode="histogram", bins=0)

    def test_profile_row_and_col_match_profile_axis(self, simple_5x4):
        row = render(simple_5x4, mode="profile_row", profile_index=1)
        explicit = render(simple_5x4, mode="profile",
                          profile_index=1, profile_axis="row")
        assert row == explicit


# ===========================================================================
# SPEC-16 — multi-format export + colorbar/title/label controls
# ===========================================================================

class TestRenderOutputFormats:
    def test_png_default(self, simple_3x3):
        assert render(simple_3x3)[:8] == PNG_MAGIC

    def test_svg_bytes(self, simple_3x3):
        result = render(simple_3x3, output_format="svg")
        assert result[:5] == SVG_MAGIC
        assert b"<svg" in result[:600]

    def test_pdf_bytes(self, simple_3x3):
        result = render(simple_3x3, output_format="pdf")
        assert result[:4] == PDF_MAGIC

    def test_unknown_format_raises(self, simple_3x3):
        with pytest.raises(InvalidParameterError):
            render(simple_3x3, output_format="tiff")

    def test_colorbar_toggle_changes_output(self, simple_3x3):
        with_cb = render(simple_3x3, colorbar=True)
        without_cb = render(simple_3x3, colorbar=False)
        assert with_cb != without_cb

    def test_title_and_labels_render(self, simple_3x3):
        result = render(simple_3x3, mode="histogram",
                        title="T", xlabel="X", ylabel="Y")
        assert result[:8] == PNG_MAGIC


# ===========================================================================
# SPEC-18 — deterministic output
# ===========================================================================

class TestRenderDeterminism:
    def test_png_byte_identical(self, simple_5x4):
        assert render(simple_5x4) == render(simple_5x4)

    def test_svg_byte_identical(self, simple_5x4):
        a = render(simple_5x4, output_format="svg")
        b = render(simple_5x4, output_format="svg")
        assert a == b

    def test_pixel_dimensions_equal_figsize_times_dpi(self, simple_5x4):
        import matplotlib.image as mimage
        png = render(simple_5x4, figsize=(6, 5), dpi=100)
        arr = mimage.imread(io.BytesIO(png), format="png")
        # No bbox_inches="tight": dimensions are exactly figsize*dpi (H, W).
        assert arr.shape[0] == 500
        assert arr.shape[1] == 600

    def test_histogram_deterministic(self, simple_5x4):
        a = render(simple_5x4, mode="histogram", bins=8)
        b = render(simple_5x4, mode="histogram", bins=8)
        assert a == b


# ===========================================================================
# SPEC-20 / SPEC-12 — thread-safe concurrent rendering
# ===========================================================================

class TestRenderConcurrency:
    def test_parallel_renders_all_valid(self, simple_5x4):
        from concurrent.futures import ThreadPoolExecutor
        modes = ["heatmap", "contour", "contourf", "histogram",
                 "profile", "surface3d"] * 4

        def _one(m):
            return render(simple_5x4, mode=m)

        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(_one, modes))

        assert len(results) == len(modes)
        for r in results:
            assert r[:8] == PNG_MAGIC

    def test_concurrent_identical_inputs_are_deterministic(self, simple_5x4):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(lambda _: render(simple_5x4), range(16)))
        # All renders of the same input must be byte-identical (SPEC-18 + lock).
        assert all(r == results[0] for r in results)


# ===========================================================================
# SPEC-14/16 — new draw_* helpers (Axes-level, shared with the GUI)
# ===========================================================================

class TestNewDrawHelpers:
    def test_draw_contourf(self, fig_ax, simple_5x4):
        from map_visualizer import draw_contourf
        fig, ax = fig_ax
        draw_contourf(ax, fig, simple_5x4, levels=6)

    def test_draw_surface3d(self, simple_5x4):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from map_visualizer import draw_surface3d
        fig = Figure(figsize=(4, 3), dpi=72)
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111, projection="3d")
        draw_surface3d(ax, fig, simple_5x4)

    def test_draw_heatmap_no_colorbar(self, fig_ax, simple_3x3):
        draw_heatmap(fig_ax[1], fig_ax[0], simple_3x3, colorbar=False)

    def test_draw_histogram_explicit_bins(self, fig_ax, simple_5x4):
        draw_histogram(fig_ax[1], simple_5x4, bins=7)


# ===========================================================================
# SPEC-15 — CSV / delimiter import + validation
# ===========================================================================

class TestLoadArrayDelimiters:
    def test_csv_inline_text(self):
        arr = load_array("1,2,3\n4,5,6\n7,8,9")
        assert arr.shape == (3, 3)
        assert arr[1, 1] == 5.0

    def test_semicolon_inline_text(self):
        arr = load_array("1;2\n3;4")
        assert arr.shape == (2, 2)
        assert arr[1, 0] == 3.0

    def test_whitespace_still_works(self):
        arr = load_array("1 2 3\n4 5 6")
        assert arr.shape == (2, 3)

    def test_csv_file(self, tmp_path, simple_3x3):
        path = tmp_path / "grid.csv"
        np.savetxt(str(path), simple_3x3, fmt="%.1f", delimiter=",")
        arr = load_array(str(path))
        assert arr.shape == (3, 3)

    def test_explicit_delimiter_overrides_sniff(self):
        arr = load_array("1,2\n3,4", delimiter=",")
        assert arr.shape == (2, 2)

    def test_unsupported_extension_csv_sibling_rejected(self, tmp_path):
        path = tmp_path / "grid.xlsx"
        path.write_text("1 2\n3 4")
        with pytest.raises(GridLoadError):
            load_array(str(path))

    def test_ragged_csv_raises_validation(self):
        with pytest.raises(GridValidationError):
            load_array("1,2,3\n4,5")


# ===========================================================================
# SPEC-22 — render-time downsampling for large grids
# ===========================================================================

class TestDownsample:
    def test_small_array_unchanged(self, simple_3x3):
        out = downsample(simple_3x3, max_cells=100)
        assert out.shape == simple_3x3.shape

    def test_zero_cap_disables(self, simple_3x3):
        out = downsample(simple_3x3, max_cells=0)
        assert out.shape == simple_3x3.shape

    def test_large_array_decimated(self):
        big = np.arange(0.0, 10000.0).reshape(100, 100)
        out = downsample(big, max_cells=400)
        assert out.size <= big.size
        assert out.size <= 400 + out.shape[0] + out.shape[1]  # best-effort bound
        assert out.ndim == 2

    def test_aspect_preserved(self):
        big = np.zeros((80, 40))
        out = downsample(big, max_cells=200)
        # same stride on both axes preserves the 2:1 ratio
        assert out.shape[0] >= out.shape[1]

    def test_render_with_max_render_cells(self):
        from map_visualizer import render
        big = np.arange(0.0, 10000.0).reshape(100, 100)
        result = render(big, mode="heatmap", max_render_cells=400)
        assert result[:8] == PNG_MAGIC


# ===========================================================================
# SPEC-21 — structured error handling (no bare/silent excepts in core)
# ===========================================================================

class TestNoBareExcepts:
    def _core_sources(self):
        import pathlib
        pkg = pathlib.Path(__file__).resolve().parent.parent / "map_visualizer"
        return [pkg / "core.py", pkg / "exceptions.py",
                pkg / "api" / "service.py"]

    def test_no_silent_except_pass(self):
        import re
        # A blanket "except ...: pass" that swallows errors is forbidden (R-2).
        bad = re.compile(r"except[^\n]*:\s*\n\s*pass\b")
        for path in self._core_sources():
            src = path.read_text(encoding="utf-8")
            assert not bad.search(src), f"silent except in {path.name}"

    def test_no_bare_except(self):
        import re
        # `except:` with no exception type is forbidden — always name the type.
        bare = re.compile(r"\n\s*except\s*:")
        for path in self._core_sources():
            src = path.read_text(encoding="utf-8")
            assert not bare.search(src), f"bare except in {path.name}"

    def test_malformed_load_names_the_cause(self):
        # A structured, message-bearing error (not a silent sentinel).
        with pytest.raises(GridValidationError) as exc_info:
            load_array("1 2 3\n4 5\n")
        assert "ragged" in str(exc_info.value).lower()

    def test_core_uses_logging_not_print(self):
        import pathlib
        pkg = pathlib.Path(__file__).resolve().parent.parent / "map_visualizer"
        src = (pkg / "core.py").read_text(encoding="utf-8")
        # No print() diagnostics in the core; it uses the logging module.
        assert "\n    print(" not in src
        assert "logging.getLogger" in src


# ===========================================================================
# SPEC-19 — figure lifecycle / memory (OO path, no pyplot, no gc.collect cult)
# ===========================================================================

class TestFigureLifecycle:
    def test_no_pyplot_or_gc_collect_in_core(self):
        import pathlib
        pkg = pathlib.Path(__file__).resolve().parent.parent / "map_visualizer"
        src = (pkg / "core.py").read_text(encoding="utf-8")
        assert "gc.collect" not in src
        assert "import matplotlib.pyplot" not in src
        assert "from matplotlib import pyplot" not in src
        assert "plt.figure" not in src

    def test_looped_renders_do_not_leak_pyplot_figures(self, simple_5x4):
        # The OO Agg path uses no global figure registry, so pyplot tracks none.
        import matplotlib.pyplot as plt
        plt.close("all")
        before = len(plt.get_fignums())
        for _ in range(30):
            render(simple_5x4, mode="heatmap")
        after = len(plt.get_fignums())
        assert after == before  # bounded — no figure accumulation

    def test_many_renders_emit_no_too_many_figures_warning(self, simple_5x4):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # promote RuntimeWarning to error
            for _ in range(25):
                render(simple_5x4, mode="heatmap")
