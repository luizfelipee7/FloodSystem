"""Environment configuration without external dependencies or implicit .env loading."""

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def resolve_path(value: str) -> Path:
    if not value.strip() or value == ":memory:":
        raise ValueError("Informe um caminho de arquivo SQLite não vazio.")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


@dataclass(frozen=True)
class Settings:
    environment: str
    database_path: Path
    require_device_auth: bool = False
    device_tokens: Mapping[str, str] | None = None
    enable_article_simulations: bool = False

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        environment = env.get("FLOODSYSTEM_ENV", "development")
        if environment not in {"development", "test", "production"}:
            raise ValueError("FLOODSYSTEM_ENV deve ser development, test ou production.")

        configured = env.get("FLOODSYSTEM_DB_PATH")
        if environment == "production" and configured is None:
            raise ValueError("Produção exige FLOODSYSTEM_DB_PATH explícito.")
        normal_path = resolve_path(configured if configured is not None else "database/development.db")
        test_path = resolve_path(env.get("FLOODSYSTEM_TEST_DB_PATH", "database/test.db"))
        if test_path in {normal_path, resolve_path("database/development.db"), resolve_path("database/production.db")}:
            raise ValueError("O banco de testes precisa ter um caminho separado do banco de desenvolvimento/produção.")
        if environment != "test" and normal_path == resolve_path("database/test.db"):
            raise ValueError("database/test.db é reservado ao ambiente de testes.")

        raw_tokens = env.get("FLOODSYSTEM_DEVICE_TOKENS_JSON", "{}")
        try:
            device_tokens = json.loads(raw_tokens)
        except json.JSONDecodeError as exc:
            raise ValueError("FLOODSYSTEM_DEVICE_TOKENS_JSON deve ser um objeto JSON válido.") from exc
        if not isinstance(device_tokens, dict) or any(
            not isinstance(device_id, str) or not device_id or
            not isinstance(token, str) or len(token) < 32 or not token.isascii()
            for device_id, token in device_tokens.items()
        ):
            raise ValueError("Configure um token ASCII de pelo menos 32 caracteres por dispositivo.")
        if len(set(device_tokens.values())) != len(device_tokens):
            raise ValueError("Cada dispositivo precisa ter um token exclusivo.")

        raw_required = env.get("FLOODSYSTEM_REQUIRE_DEVICE_AUTH", "false").lower()
        if raw_required not in {"true", "false"}:
            raise ValueError("FLOODSYSTEM_REQUIRE_DEVICE_AUTH deve ser true ou false.")
        require_device_auth = environment == "production" or raw_required == "true"
        if require_device_auth and not device_tokens:
            raise ValueError("Autenticação de dispositivos exige ao menos um token configurado.")
        article_flag = env.get("FLOODSYSTEM_ENABLE_ARTICLE_SIMULATIONS", "false").lower()
        if article_flag not in {"true", "false"}:
            raise ValueError("FLOODSYSTEM_ENABLE_ARTICLE_SIMULATIONS deve ser true ou false.")
        effective_path = test_path if environment == "test" else normal_path
        article_enabled = article_flag == "true"
        if article_enabled and (environment == "production" or effective_path in {
                resolve_path("database/development.db"), resolve_path("database/production.db")}):
            raise ValueError("Ensaios meteorológicos exigem banco próprio fora de produção/desenvolvimento normal.")
        return cls(environment, effective_path, require_device_auth, device_tokens, article_enabled)
