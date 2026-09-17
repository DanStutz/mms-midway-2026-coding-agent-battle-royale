"""A non-operational YellowKey/BitLocker attack-path simulator.

This program models the security assumptions involved in the publicly
reported YellowKey issue. It does not interact with BitLocker, WinRE, USB
devices, firmware, disks, or the host filesystem. It is intended for demos,
training, and blog screenshots.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum


class Outcome(Enum):
    BLOCKED = "blocked"
    EXPOSED = "exposed"


@dataclass
class LabConfig:
    patched: bool = False
    physical_access: bool = True
    recovery_boot_available: bool = True
    removable_media_allowed: bool = True
    tpm_only: bool = True
    external_boot_locked: bool = False


def emit(stage: str, message: str) -> None:
    print(f"[{stage:<12}] {message}")


def simulate(config: LabConfig) -> Outcome:
    print("YELLOWKEY CONCEPTUAL SIMULATION - NO SYSTEM CHANGES\n")

    emit("ASSUMPTIONS", f"patched={config.patched}")
    emit("ASSUMPTIONS", f"TPM-only BitLocker={config.tpm_only}")

    if not config.physical_access:
        emit("PRECONDITION", "No physical access: attack path unavailable.")
        return Outcome.BLOCKED

    emit("PRECONDITION", "Physical access is present.")

    if config.external_boot_locked or not config.removable_media_allowed:
        emit("CONTROL", "Firmware/device policy blocks removable-media boot.")
        return Outcome.BLOCKED

    if not config.recovery_boot_available:
        emit("CONTROL", "Recovery boot is unavailable or disabled.")
        return Outcome.BLOCKED

    emit("STAGE 1", "Attacker reaches the recovery environment.")

    if config.patched:
        emit("STAGE 2", "Recovery processing rejects the vulnerable behavior.")
        emit("RESULT", "WinRE remains constrained; encrypted data is not exposed.")
        return Outcome.BLOCKED

    emit("STAGE 2", "A crafted recovery artifact crosses a trust boundary.")
    emit("STAGE 3", "The normal recovery-shell configuration is modeled as altered.")
    emit("STAGE 4", "Recovery falls back to a more powerful local shell.")

    if config.tpm_only:
        emit("STAGE 5", "The model assumes automatic TPM-backed volume unlock.")
        emit("RESULT", "System-volume contents become readable in the simulation.")
        emit("IMPACT", "Confidentiality and integrity of local data are at risk.")
        return Outcome.EXPOSED

    emit("STAGE 5", "A separate preboot factor is required in this configuration.")
    emit("RESULT", "This simplified model stops before volume access.")
    return Outcome.BLOCKED


def parse_args() -> LabConfig:
    parser = argparse.ArgumentParser(
        description="Model YellowKey attack prerequisites without performing an exploit."
    )
    parser.add_argument(
        "--patched", action="store_true", help="Model a system with the vendor fix applied."
    )
    parser.add_argument(
        "--no-physical-access", action="store_true", help="Remove the physical-access prerequisite."
    )
    parser.add_argument(
        "--lock-external-boot", action="store_true", help="Model firmware blocking removable-media boot."
    )
    parser.add_argument(
        "--disable-recovery", action="store_true", help="Model recovery boot being unavailable."
    )
    parser.add_argument(
        "--preboot-factor", action="store_true", help="Model a non-TPM-only preboot configuration."
    )
    args = parser.parse_args()
    return LabConfig(
        patched=args.patched,
        physical_access=not args.no_physical_access,
        recovery_boot_available=not args.disable_recovery,
        removable_media_allowed=not args.lock_external_boot,
        tpm_only=not args.preboot_factor,
        external_boot_locked=args.lock_external_boot,
    )


if __name__ == "__main__":
    result = simulate(parse_args())
    print(f"\nFinal modeled outcome: {result.value.upper()}")
