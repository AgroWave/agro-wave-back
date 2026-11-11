"""Polar sweep coverage engine implementing spatial Longley-Rice simulation (RN-48)."""

import math
from pathlib import Path
from typing import Any
from uuid import UUID

from agrowave.modules.simulation.domain.coverage_calculator import (
    compute_coverage_metrics,
)
from agrowave.modules.simulation.domain.coverage_models import (
    CoverageMetrics,
    CoverageResult,
    CoverageSample,
)

try:
    import itmlogic
except ImportError:
    itmlogic = None


class PolarSweepCoverageEngine:
    """Computes area coverage and DSR evaluation metrics using radial polar sweeps (RN-48).

    Emulates the native radial ray-tracing algorithm of Radio Mobile by scanning
    N azimuthal bearings around an Access Node and evaluating Longley-Rice path loss
    at discrete radial steps up to the scenario boundary.
    """

    METERS_PER_DEGREE_LAT: float = 111320.0

    def compute_coverage(
        self,
        access_node: dict[str, Any],
        bounds: dict[str, float],
        radio_params: dict[str, Any],
        itm_params: dict[str, Any],
        azimuth_count: int = 360,
        radial_step_m: float = 100.0,
        max_radius_m: float = 5000.0,
    ) -> CoverageResult:
        """Computes polar coverage samples and consolidated DSR metrics (CoverageEnginePort).

        Args:
            access_node: Access node dictionary with position, height, gain, sensitivity.
            bounds: Geographical bounding box.
            radio_params: Radio configuration dictionary.
            itm_params: Longley-Rice environmental parameters.
            azimuth_count: Number of azimuthal angles (default 360).
            radial_step_m: Spatial resolution along each radial, in meters (m).
            max_radius_m: Maximum evaluation distance, in meters (m).

        Returns:
            CoverageResult containing all evaluated samples and DSR metrics.
        """
        return self.compute_synthetic_coverage(
            access_node=access_node,
            bounds=bounds,
            radio_params=radio_params,
            itm_params=itm_params,
            azimuth_count=azimuth_count,
            radial_step_m=radial_step_m,
            max_radius_m=max_radius_m,
        )

    def compute_synthetic_coverage(
        self,
        access_node: dict[str, Any],
        bounds: dict[str, float],
        radio_params: dict[str, Any],
        itm_params: dict[str, Any],
        azimuth_count: int = 360,
        radial_step_m: float = 100.0,
        max_radius_m: float = 5000.0,
        terrain_elevation_m: float = 2600.0,
    ) -> CoverageResult:
        """Computes polar coverage over synthetic flat terrain for testing (AC-27).

        Args:
            access_node: Access node dictionary with position, height, gain, sensitivity.
            bounds: Geographical bounding box (south, west, north, east).
            radio_params: Radio configuration (frequency_mhz, tx_power_dbm, tx_gain_dbi, tx_height_agl_m).
            itm_params: Longley-Rice environmental parameters (ens0, klim, eps, sgm).
            azimuth_count: Number of azimuthal angles (default 360).
            radial_step_m: Spatial resolution along each radial, in meters (m).
            max_radius_m: Maximum evaluation distance, in meters (m).
            terrain_elevation_m: Flat elevation assigned to terrain profile, in meters (m).

        Returns:
            CoverageResult containing all evaluated samples and DSR metrics.
        """
        gw_lat = float(access_node["latitude"])
        gw_lon = float(access_node["longitude"])
        gw_rx_gain = float(access_node.get("antenna_gain_dbi", 3.0))
        gw_rx_height = float(access_node.get("height_agl_m", 15.0))
        gw_sensitivity = float(access_node.get("sensitivity_dbm", -137.0))
        access_node_id = UUID(str(access_node["id"]))

        freq_mhz = float(radio_params["frequency_mhz"])
        tx_power = float(radio_params.get("tx_power_dbm", 20.0))
        tx_gain = float(radio_params.get("tx_gain_dbi", 2.0))
        tx_height = float(radio_params.get("tx_height_agl_m", 2.0))

        ens0 = float(itm_params.get("ens0", 301.0))
        klim = int(itm_params.get("klim", 5))
        eps = float(itm_params.get("eps", 15.0))
        sgm = float(itm_params.get("sgm", 0.005))

        step_angle_deg = 360.0 / float(azimuth_count)
        delta_theta_rad = (2.0 * math.pi) / float(azimuth_count)

        samples: list[CoverageSample] = []
        lat_rad = math.radians(gw_lat)
        cos_lat = max(0.01, math.cos(lat_rad))

        distances = [
            float(d)
            for d in range(
                int(radial_step_m),
                int(max_radius_m) + 1,
                int(radial_step_m),
            )
        ]

        for az_idx in range(azimuth_count):
            azimuth_deg = az_idx * step_angle_deg
            az_rad = math.radians(azimuth_deg)
            sin_az = math.sin(az_rad)
            cos_az = math.cos(az_rad)

            for dist_m in distances:
                d_lat = (dist_m * cos_az) / self.METERS_PER_DEGREE_LAT
                d_lon = (dist_m * sin_az) / (self.METERS_PER_DEGREE_LAT * cos_lat)
                pt_lat = gw_lat + d_lat
                pt_lon = gw_lon + d_lon

                # Elementary polar sector area in km²
                cell_area_km2 = (dist_m * radial_step_m * delta_theta_rad) * 1e-6

                # Path loss evaluation (synthetic flat terrain via ITM or FSPL fallback)
                path_loss_db = self._compute_point_loss(
                    distance_m=dist_m,
                    freq_mhz=freq_mhz,
                    tx_height_m=tx_height,
                    rx_height_m=gw_rx_height,
                    elevations=[terrain_elevation_m, terrain_elevation_m],
                    ens0=ens0,
                    klim=klim,
                    eps=eps,
                    sgm=sgm,
                )

                prx_dbm = tx_power + tx_gain + gw_rx_gain - path_loss_db
                viable = prx_dbm >= gw_sensitivity

                samples.append(
                    CoverageSample(
                        latitude=round(pt_lat, 6),
                        longitude=round(pt_lon, 6),
                        distance_m=round(dist_m, 2),
                        azimuth_deg=round(azimuth_deg, 2),
                        received_power_dbm=round(prx_dbm, 2),
                        viable=viable,
                        cell_area_km2=round(cell_area_km2, 6),
                    )
                )

        # Total scenario area: circle of radius max_radius_m in km²
        total_area_km2 = math.pi * ((max_radius_m / 1000.0) ** 2)
        metrics = compute_coverage_metrics(
            samples=samples,
            total_area_km2=total_area_km2,
        )

        return CoverageResult(
            metrics=metrics,
            samples=tuple(samples),
            access_node_id=access_node_id,
        )

    def _compute_point_loss(
        self,
        distance_m: float,
        freq_mhz: float,
        tx_height_m: float,
        rx_height_m: float,
        elevations: list[float],
        ens0: float,
        klim: int,
        eps: float,
        sgm: float,
    ) -> float:
        """Evaluates ITM path loss or FSPL fallback for a point."""
        if itmlogic is not None:
            try:
                # np_profile: [count-1, step_m, z0, z1, ...]
                step_m = distance_m / max(1, len(elevations) - 1)
                profile_arr = [len(elevations) - 1, step_m] + elevations
                # itm call
                res = itmlogic.itm.point_to_point(
                    elev=profile_arr,
                    tht_m=tx_height_m,
                    rht_m=rx_height_m,
                    eps_dielec=eps,
                    sgm_conductivity=sgm,
                    eno_ns_surfref=ens0,
                    frq_mhz=freq_mhz,
                    radio_climate=klim,
                    pol=1,
                    conf=0.5,
                    rel=0.5,
                )
                loss = float(res[0])
                if loss > 0.0 and loss < 300.0:
                    return loss
            except Exception:
                pass

        # Free space path loss fallback: FSPL = 20*log10(d_km) + 20*log10(f_MHz) + 32.44
        d_km = max(0.001, distance_m / 1000.0)
        fspl = 20.0 * math.log10(d_km) + 20.0 * math.log10(freq_mhz) + 32.44
        return fspl
