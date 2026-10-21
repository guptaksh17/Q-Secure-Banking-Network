"""Shared BB84 data types (kept separate so channel.py and bb84.py avoid an import cycle)."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PreparedStates:
    """BB84 states in flight: qubit i is |bits[i]> encoded in bases[i]."""

    bits: np.ndarray
    bases: np.ndarray

    def __post_init__(self):
        if self.bits.shape != self.bases.shape or self.bits.ndim != 1:
            raise ValueError("bits and bases must be 1-D arrays of equal length")

    def __len__(self) -> int:
        return int(self.bits.size)
