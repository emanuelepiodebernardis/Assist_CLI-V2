from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ModelsConfig(BaseModel):
    """Tier di modelli (v4.0 Proof Engine).

    - fast: agenti dello sciame (generazione test boundary, analisi
      preliminari). Economico, alto volume.
    - strong: judge finale e scrittura fix. Costoso, basso volume.
    """

    fast: str = "claude-haiku-4-5"
    strong: str = "claude-sonnet-4-6"


class VerifyConfig(BaseModel):
    """Parametri della pipeline di verifica (v4.0 Proof Engine)."""

    mutation_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    sandbox_timeout_seconds: int = Field(default=30, ge=1)
    max_mutants: int = Field(default=40, ge=1)
    generate_boundary_tests: bool = True
    use_docker: bool = False


class QualityConfig(BaseModel):
    threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    max_self_corrections: int = Field(default=2, ge=0)


class VerificationConfig(BaseModel):
    check_syntax: bool = True
    check_placeholders: bool = True
    check_coherence: bool = True


class LoggingConfig(BaseModel):
    level: str = "INFO"


class Settings(BaseModel):
    model: str = "claude-sonnet-4-6"
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_input_tokens: int = Field(default=4000, ge=1)
    output_mode: str = "concise"

    models: ModelsConfig = Field(default_factory=ModelsConfig)
    verify: VerifyConfig = Field(default_factory=VerifyConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


_DEFAULT_CONFIG_PATH = "config/settings.yaml"


class ConfigLoader:
    def __init__(
        self,
        config_path: str | Path = _DEFAULT_CONFIG_PATH,
    ) -> None:
        self.config_path = Path(config_path)
        self._is_default = str(config_path) == _DEFAULT_CONFIG_PATH

    def load(self) -> Settings:
        """Carica le impostazioni.

        Ordine di risoluzione per il path di default:
        1. `config/settings.yaml` relativo alla directory corrente;
        2. `config/settings.yaml` relativo alla root del package
           (permette di eseguire `assist` da qualunque directory);
        3. default Pydantic di `Settings`.

        Un path custom esplicito mancante solleva FileNotFoundError.
        """

        path = self.config_path

        if not path.exists() and self._is_default:
            package_root = Path(__file__).resolve().parents[2]
            fallback = package_root / _DEFAULT_CONFIG_PATH

            if fallback.exists():
                path = fallback
            else:
                return Settings()

        if not path.exists():
            raise FileNotFoundError(
                f"Config file not found: {path}"
            )

        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

        return Settings.model_validate(data)