from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.core.capabilities import detect_capabilities

router = APIRouter(tags=["system"])

DISCLAIMER = (
    "Educational software simulation. Not a real banking network, not quantum "
    "hardware, and not production-grade QKD security."
)


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "disclaimer": DISCLAIMER,
        "qkd_defaults": {
            "qber_threshold": settings.qber_threshold,
            "qber_sample_fraction": settings.qber_sample_fraction,
            "default_qubits": settings.default_qubits,
            "quantum_backend": settings.quantum_backend,
        },
        "capabilities": detect_capabilities(),
    }
