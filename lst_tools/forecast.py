"""Honest heat forecasting from the real yearly LST stack.

Two products, kept deliberately distinct:

1. ``lst_warming_rate`` — the **measured** trend. A per-pixel linear fit over
   the real yearly summer surfaces gives °C/decade of warming so far. This is
   not a prediction; it is what the data already shows.

2. ``lst_project`` — a **projection**. It extends that same linear trend to a
   future year, *if the last decade's rate continued*, and returns an
   uncertainty figure. It is extrapolation, labelled as such everywhere it is
   shown — it does not model climate feedbacks, policy, or anything beyond the
   straight line the past decade drew.
"""
import numpy as np

__all__ = ["lst_trend", "lst_warming_rate", "lst_project", "current_year_anomaly"]


def lst_trend(arrays, years):
    """Per-pixel linear regression over the yearly LST stack.

    arrays: list of 2-D rasters (same shape, NaN outside Germany / cloud).
    years:  matching list of ints.
    Returns slope (°C/yr), intercept (°C at year 0), and sigma (residual
    std, °C) per pixel; pixels missing any year are NaN.
    """
    A = np.stack([np.asarray(a, float) for a in arrays])      # (T,H,W)
    t = np.asarray(years, float)
    T = len(t)
    valid = np.all(np.isfinite(A), axis=0)                    # need every year
    tc = t - t.mean()
    den = float((tc ** 2).sum())
    with np.errstate(invalid="ignore", divide="ignore"):
        Am = np.where(np.isfinite(A), A, np.nan)
        ymean = np.where(valid, np.nanmean(np.where(np.isfinite(A), A, 0), axis=0), np.nan)
    slope = np.tensordot(tc, np.nan_to_num(A), axes=(0, 0)) / den
    intercept = ymean - slope * t.mean()
    pred = intercept[None] + slope[None] * t[:, None, None]
    resid = A - pred
    sigma = np.sqrt(np.nansum(resid ** 2, axis=0) / max(T - 2, 1))
    for arr in (slope, intercept, sigma):
        arr[~valid] = np.nan
    return slope, intercept, sigma, den, float(t.mean())


def lst_warming_rate(arrays, years, vlim=2.0, alpha=0.9):
    """Measured warming map: °C per decade per pixel, as a diverging PNG.

    The per-pixel slope can show hard scene-tile edges where early years have
    sparser coverage; we gap-fill thin seams and lightly smooth so the trend
    reads as a continuous field, not a patchwork. Returns png + national rate.
    """
    from .surface import surface_png_stops, ANOM_STOPS, fill_small_gaps
    slope, _, _, _, _ = lst_trend(arrays, years)
    rate_decade = slope * 10.0                                # °C per decade
    rate_decade = fill_small_gaps(rate_decade, max_gap_px=8)  # bridge tile seams
    try:                                                     # gentle smoothing
        from scipy import ndimage
        m = np.isnan(rate_decade)
        filled = np.where(m, 0.0, rate_decade)
        w = (~m).astype(float)
        num = ndimage.gaussian_filter(filled, 1.2)
        den = ndimage.gaussian_filter(w, 1.2)
        sm = np.where(den > 0, num / den, np.nan)
        rate_decade = np.where(m, np.nan, sm)
    except Exception:
        pass
    png = surface_png_stops(rate_decade, ANOM_STOPS, vmin=-vlim, vmax=vlim, alpha=alpha)
    national = float(np.nanmean(rate_decade))
    return {"png": png, "rate": rate_decade,
            "national_per_decade": round(national, 2),
            "vlim": vlim}


def lst_project(arrays, years, to_year, baseline=None, vmin=15, vmax=45, alpha=0.9):
    """Project the measured linear trend to ``to_year`` (extrapolation).

    Returns: png (projected surface), mean_temp, increase_vs_baseline,
    and uncertainty (mean projection std, °C) — all clearly a projection.
    """
    from .surface import surface_png_stops, HEAT_STOPS
    slope, intercept, sigma, den, tmean = lst_trend(arrays, years)
    proj = intercept + slope * float(to_year)
    png = surface_png_stops(proj, HEAT_STOPS, vmin=vmin, vmax=vmax, alpha=alpha)
    mean_temp = float(np.nanmean(proj))
    # projection standard error at to_year (mean over valid pixels)
    T = len(years)
    se = sigma * np.sqrt(1.0 / T + (float(to_year) - tmean) ** 2 / den)
    uncertainty = float(np.nanmean(se))
    out = {"png": png, "year": int(to_year),
           "mean_temp": round(mean_temp, 1),
           "uncertainty": round(uncertainty, 1)}
    if baseline is not None:
        out["increase_vs_baseline"] = round(mean_temp - baseline, 1)
    return out


def current_year_anomaly(current_arr, median_arr, bounds, year, cities=None,
                         grid_current=None, grid_median=None, baseline_label="2016–2025",
                         vlim=6.0, alpha=0.9, note=None, max_plausible=5.0,
                         min_coverage=0.5):
    """Build the 'this summer vs the 10-year normal' payload for build_heat_story.

    Carries ABSOLUTE values (this-summer °C and the normal °C) next to every
    relative delta, so the story can show "30.2°C vs 29.2°C normal (+1.0°C)"
    rather than a bare "+1°C". A partial summer is noisy, so per-city deltas
    beyond ``max_plausible`` °C are dropped as measurement artefacts rather than
    published as if real.
    """
    from .surface import surface_png_stops, ANOM_STOPS, fill_small_gaps
    cur = np.asarray(current_arr, float)
    med = np.asarray(median_arr, float)
    delta = cur - med                                  # hotter/cooler than normal
    delta = fill_small_gaps(delta, max_gap_px=6)
    png = surface_png_stops(delta, ANOM_STOPS, vmin=-vlim, vmax=vlim, alpha=alpha)
    nat_now = float(np.nanmean(cur))
    nat_norm = float(np.nanmean(med))
    out = {"png": png, "year": int(year),
           "national_delta": round(nat_now - nat_norm, 1),
           "national_now": round(nat_now, 1),
           "national_normal": round(nat_norm, 1),
           "baseline_label": baseline_label,
           "grid_now": grid_current,            # for click-to-read on the 2026 view
           "bounds": [[bounds[0][0], bounds[0][1]], [bounds[1][0], bounds[1][1]]]
                     if isinstance(bounds[0], (list, tuple)) else bounds,
           "note": note}
    # per-city: sample a NEIGHBOURHOOD mean (not one pixel) so a single hot pass
    # can't spike a city; require enough valid pixels, and drop implausible deltas.
    if cities and grid_current and grid_median:
        H, W = cur.shape
        s, w = bounds[0] if isinstance(bounds[0], (list, tuple)) else (bounds[0], bounds[1])
        n, e = bounds[1] if isinstance(bounds[0], (list, tuple)) else (bounds[2], bounds[3])
        rows, dropped = [], 0
        rad = max(2, int(W * 0.012))                   # ~1% of width neighbourhood
        for name, lon, lat in cities:
            if not (s <= lat <= n and w <= lon <= e):
                continue
            col = int((lon - w) / (e - w) * (W - 1))
            row = int((n - lat) / (n - s) * (H - 1))
            r0, r1 = max(0, row - rad), min(H, row + rad + 1)
            c0, c1 = max(0, col - rad), min(W, col + rad + 1)
            cwin = cur[r0:r1, c0:c1]; mwin = med[r0:r1, c0:c1]
            cov = np.isfinite(cwin).mean()             # fraction of valid pixels nearby
            if cov < min_coverage:                     # too little 2026 data here
                dropped += 1
                continue
            a = float(np.nanmean(cwin)); b = float(np.nanmean(mwin))
            d = round(a - b, 1)
            if abs(d) > max_plausible:                 # still implausible -> artefact
                dropped += 1
                continue
            rows.append({"name": name, "now": round(a, 1),
                         "normal": round(b, 1), "delta": d})
        rows.sort(key=lambda r: r["delta"], reverse=True)
        out["cities"] = rows
        out["cities_dropped"] = dropped
    return out
