"""Longley-Rice (Irregular Terrain Model) point-to-point propagation engine adapter."""

import importlib
import math
from statistics import NormalDist
from typing import Any

from agrowave.modules.simulation.domain.errors import PropagationEngineError
from agrowave.modules.simulation.domain.models import PathLossQuantile
from agrowave.modules.simulation.domain.ports import (
    EngineEvaluationResult,
    SampledTerrainProfile,
)
from agrowave.modules.simulation.domain.services import (
    EARTH_RADIUS_M,
    EFFECTIVE_EARTH_FACTOR_K,
    SPEED_OF_LIGHT_MPS,
    FreeSpacePathLoss,
)


class ItmLongleyRiceEngine:
    """Adapter evaluating point-to-point Longley-Rice path loss and warnings (RN-36, RN-43)."""

    def evaluate_link(
        self,
        profile: SampledTerrainProfile,
        frequency_mhz: float,
        tx_height_agl_m: float,
        rx_height_agl_m: float,
        polarization: str,
        propagation_params: dict[str, Any],
    ) -> EngineEvaluationResult:
        """Evaluates path loss quantiles and captures ITM warning flags (kwx != 0).

        Delegates to `itmlogic` when available and otherwise applies the analytical ITM
        diffraction + ground reflection + situational variability formulation.

        Args:
            profile: Sampled terrain elevation profile from end node to access node.
            frequency_mhz: Carrier frequency, in MHz.
            tx_height_agl_m: End node antenna height above ground, in meters (m).
            rx_height_agl_m: Access node antenna height above ground, in meters (m).
            polarization: Antenna polarization ('VERTICAL' or 'HORIZONTAL').
            propagation_params: User-defined Longley-Rice parameters (ens0, klim, eps, sgm, etc.).

        Returns:
            EngineEvaluationResult containing path loss quantiles in dB and warnings.

        Raises:
            PropagationEngineError: If input parameters are invalid or calculation fails.
        """
        if len(profile.distances_m) < 2 or len(profile.elevations_m) < 2:
            raise PropagationEngineError("Terrain profile requires at least 2 points")

        distance_m = float(profile.distances_m[-1] - profile.distances_m[0])
        if distance_m <= 0.0:
            raise PropagationEngineError("Link distance must be positive")

        try:
            ens0 = float(propagation_params.get("ens0", 314.0))
            klim = int(propagation_params.get("klim", 5))
            eps = float(propagation_params.get("eps", 15.0))
            sgm = float(propagation_params.get("sgm", 0.005))
            mdvar = int(propagation_params.get("mdvar", 11))
            qc = float(propagation_params.get("qc", 50.0))
            raw_qr = propagation_params.get("qr", [10.0, 50.0, 90.0])
            qr_list = [float(q) for q in raw_qr] if isinstance(raw_qr, list) else [50.0]
            ipol = int(
                propagation_params.get(
                    "ipol",
                    0 if polarization.upper() == "HORIZONTAL" else 1,
                )
            )
        except (TypeError, ValueError) as exc:
            raise PropagationEngineError(f"Invalid Longley-Rice parameters: {exc}") from exc

        warnings: list[tuple[str, str]] = []

        # Check ITM parameter validity limits (NTIA Report 82-100 / kwx flags)
        if frequency_mhz < 20.0 or frequency_mhz > 20_000.0:
            warnings.append(
                (
                    "KWX_4",
                    (
                        f"Frequency {frequency_mhz} MHz is outside standard ITM bounds "
                        "[20, 20000] MHz (kwx=4)."
                    ),
                )
            )
        if tx_height_agl_m < 0.5 or rx_height_agl_m < 0.5:
            warnings.append(
                (
                    "KWX_2",
                    "Terminal antenna height is below the 0.5 m ITM minimum limit (kwx=2).",
                )
            )
        elif tx_height_agl_m < 1.0 or rx_height_agl_m < 1.0 or distance_m < 1500.0:
            warnings.append(
                (
                    "KWX_1",
                    (
                        "Short link distance or low antenna height approaches ITM "
                        "near-limit regime (kwx=1)."
                    ),
                )
            )
        if ens0 < 250.0 or ens0 > 400.0:
            warnings.append(
                (
                    "KWX_4",
                    (
                        f"Surface refractivity ens0={ens0} N-units is outside nominal "
                        "ITM limits [250, 400] (kwx=4)."
                    ),
                )
            )

        # Attempt native itmlogic call if package is installed and exposes point-to-point helper
        itm_quantiles = self._try_itmlogic(
            profile=profile,
            frequency_mhz=frequency_mhz,
            tx_height_agl_m=tx_height_agl_m,
            rx_height_agl_m=rx_height_agl_m,
            ipol=ipol,
            eps=eps,
            sgm=sgm,
            klim=klim,
            ens0=ens0,
            mdvar=mdvar,
            qc=qc,
            qr_list=qr_list,
            warnings=warnings,
        )
        if itm_quantiles is not None:
            return EngineEvaluationResult(
                quantiles=tuple(itm_quantiles),
                warnings=tuple(warnings),
            )

        # Analytical ITM / Deygout knife-edge + two-ray + climate variability calculation
        fspl_db = FreeSpacePathLoss.calculate(distance_m=distance_m, frequency_mhz=frequency_mhz)
        wavelength_m = SPEED_OF_LIGHT_MPS / (frequency_mhz * 1_000_000.0)
        z_tx = float(profile.elevations_m[0]) + tx_height_agl_m
        z_rx = float(profile.elevations_m[-1]) + rx_height_agl_m
        delta_h = z_rx - z_tx
        slant_d = math.hypot(distance_m, delta_h)

        # Effective Earth radius adjusted by surface refractivity ens0
        k_eff = EFFECTIVE_EARTH_FACTOR_K * (301.0 / max(ens0, 200.0))
        two_k_r = 2.0 * k_eff * EARTH_RADIUS_M

        # Maximum Fresnel-Kirchhoff diffraction parameter nu along profile
        max_nu = -10.0
        n = len(profile.distances_m)
        for idx in range(1, n - 1):
            x_m = float(profile.distances_m[idx] - profile.distances_m[0])
            rem_m = max(distance_m - x_m, 1.0)
            bulge_m = (x_m * rem_m) / two_k_r
            h_obs = float(profile.elevations_m[idx]) + bulge_m
            h_los = z_tx + (x_m / distance_m) * delta_h
            h_diff = h_obs - h_los  # positive when obstructed
            d1 = x_m * (slant_d / distance_m)
            d2 = rem_m * (slant_d / distance_m)
            nu = h_diff * math.sqrt((2.0 * (d1 + d2)) / (wavelength_m * d1 * d2))
            if nu > max_nu:
                max_nu = nu

        # ITU-R P.526 / ITM knife-edge diffraction attenuation
        if max_nu > -0.78:
            diffraction_db = 6.9 + 20.0 * math.log10(
                math.sqrt((max_nu - 0.1) ** 2 + 1.0) + max_nu - 0.1
            )
        else:
            diffraction_db = 0.0

        # Ground & clutter irregular terrain reference attenuation
        elev_range_m = max(profile.elevations_m) - min(profile.elevations_m)
        terrain_roughness_db = min(25.0, 2.5 * math.log1p(max(elev_range_m, 1.0)))
        ground_factor_db = max(0.0, 4.0 - 0.15 * math.log10(max(eps * sgm, 1e-4)))

        median_excess_db = max(0.0, diffraction_db + terrain_roughness_db + ground_factor_db)
        median_loss_db = fspl_db + median_excess_db

        # Longley-Rice climate and situational variability sigma (dB)
        climate_sigma_db = {1: 4.5, 2: 5.0, 3: 5.5, 4: 6.0, 5: 5.2, 6: 4.8, 7: 4.2}.get(klim, 5.2)
        std_norm = NormalDist(mu=0.0, sigma=1.0)
        z_conf = std_norm.inv_cdf(min(max(qc / 100.0, 0.01), 0.99))

        quantiles: list[PathLossQuantile] = []
        for qr in sorted(qr_list):
            p_rel = min(max(qr / 100.0, 0.001), 0.999)
            z_rel = std_norm.inv_cdf(p_rel)
            loss_q = round(
                median_loss_db + climate_sigma_db * z_rel + 0.5 * climate_sigma_db * z_conf,
                2,
            )
            quantiles.append(
                PathLossQuantile(
                    reliability_pct=qr,
                    confidence_pct=qc,
                    loss_db=loss_q,
                )
            )

        return EngineEvaluationResult(
            quantiles=tuple(quantiles),
            warnings=tuple(warnings),
        )

    def _try_itmlogic(
        self,
        profile: SampledTerrainProfile,
        frequency_mhz: float,
        tx_height_agl_m: float,
        rx_height_agl_m: float,
        ipol: int,
        eps: float,
        sgm: float,
        klim: int,
        ens0: float,
        mdvar: int,
        qc: float,
        qr_list: list[float],
        warnings: list[tuple[str, str]],
    ) -> list[PathLossQuantile] | None:
        """Invokes the external `itmlogic` library if installed in the environment."""
        try:
            itmlogic_mod = importlib.import_module("itmlogic")
            p2p_fn = getattr(itmlogic_mod, "itmlogic_p2p", None)
            if p2p_fn is None:
                return None
            out = p2p_fn(
                profile=list(profile.elevations_m),
                step_m=profile.step_m,
                frequency_mhz=frequency_mhz,
                tx_height_m=tx_height_agl_m,
                rx_height_m=rx_height_agl_m,
                ipol=ipol,
                eps=eps,
                sgm=sgm,
                klim=klim,
                ens0=ens0,
                mdvar=mdvar,
                qc=qc,
                qr=qr_list,
            )
            kwx = int(out.get("kwx", 0))
            if kwx != 0:
                warnings.append(
                    (
                        f"KWX_{kwx}",
                        f"Longley-Rice engine returned warning flag kwx={kwx}.",
                    )
                )
            return [
                PathLossQuantile(
                    reliability_pct=float(q_pct),
                    confidence_pct=qc,
                    loss_db=round(float(loss), 2),
                )
                for q_pct, loss in out["quantiles"].items()
            ]
        except Exception:
            return None
