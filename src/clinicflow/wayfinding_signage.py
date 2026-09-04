"""Assess temporary wayfinding signage during room relocations."""

from dataclasses import dataclass

from .models import DomainError


@dataclass(frozen=True, slots=True)
class WayfindingRequirement:
    route_id: str
    destination: str
    decision_points: int
    accessible_route: bool = False


@dataclass(frozen=True, slots=True)
class WayfindingObservation:
    route_id: str
    signs_installed: int
    accessible_symbols: bool
    destination_matches: bool


@dataclass(frozen=True, slots=True)
class WayfindingFinding:
    route_id: str
    destination: str
    missing_signs: int
    blockers: tuple[str, ...]
    ready: bool


def assess_wayfinding_signage(
    requirements: list[WayfindingRequirement], observations: list[WayfindingObservation]
) -> list[WayfindingFinding]:
    """Reconcile signs at decision points and accessible-route markings."""
    configured: dict[str, WayfindingRequirement] = {}
    for requirement in requirements:
        route_id = _text(requirement.route_id, "wayfinding route id")
        destination = _text(requirement.destination, "wayfinding destination")
        key = route_id.casefold()
        if (
            key in configured
            or not isinstance(requirement.decision_points, int)
            or isinstance(requirement.decision_points, bool)
            or requirement.decision_points < 1
        ):
            raise DomainError("invalid or duplicate wayfinding requirement")
        configured[key] = WayfindingRequirement(
            route_id, destination, requirement.decision_points, requirement.accessible_route
        )
    observed: dict[str, WayfindingObservation] = {}
    for observation in observations:
        route_id = _text(observation.route_id, "wayfinding observation route")
        key = route_id.casefold()
        if (
            key not in configured
            or key in observed
            or not isinstance(observation.signs_installed, int)
            or isinstance(observation.signs_installed, bool)
            or observation.signs_installed < 0
        ):
            raise DomainError("invalid or duplicate wayfinding observation")
        observed[key] = observation
    findings: list[WayfindingFinding] = []
    for key, requirement in configured.items():
        matched_observation = observed.get(key)
        installed = matched_observation.signs_installed if matched_observation else 0
        blockers: list[str] = []
        if matched_observation is None:
            blockers.append("inspection_missing")
        if installed < requirement.decision_points:
            blockers.append("decision_point_signs_missing")
        if requirement.accessible_route and (matched_observation is None or not matched_observation.accessible_symbols):
            blockers.append("accessible_symbols_missing")
        if matched_observation is not None and not matched_observation.destination_matches:
            blockers.append("destination_mismatch")
        findings.append(
            WayfindingFinding(
                requirement.route_id,
                requirement.destination,
                max(0, requirement.decision_points - installed),
                tuple(blockers),
                not blockers,
            )
        )
    return sorted(findings, key=lambda row: (row.ready, -len(row.blockers), row.route_id))


def _text(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise DomainError(f"{field} is required")
    return normalized
