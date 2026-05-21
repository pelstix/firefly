from __future__ import annotations

from enum import Enum
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    LOCAL = "local"
    CI = "ci"
    STAGING = "staging"


class User(str, Enum):
    USER1 = "test1"
    USER2 = "test2"


USER_CREDENTIALS: dict[User, str] = {
    User.USER1: "test123",
    User.USER2: "test456",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_base_url: str = Field(default="http://localhost:8080")
    swagger_doc_path: str = Field(default="/swagger/doc.json")

    user1_name: str = Field(default="test1")
    user1_password: str = Field(default="test123")
    user2_name: str = Field(default="test2")
    user2_password: str = Field(default="test456")

    request_timeout: int = Field(default=30)
    service_startup_timeout: int = Field(default=60)
    service_startup_poll_interval: float = Field(default=1.0)

    load_test_users: int = Field(default=20)
    load_test_spawn_rate: int = Field(default=10)
    load_test_duration: str = Field(default="60s")
    load_test_min_rps: float = Field(default=1000 / 60)
    load_test_max_failure_rate: float = Field(default=0.01)
    load_test_max_p95_ms: float = Field(default=500.0)

    report_dir: str = Field(default="reports")
    environment: Environment = Field(default=Environment.LOCAL)

    @field_validator("api_base_url", mode="before")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return str(v).rstrip("/")

    @property
    def swagger_doc_url(self) -> str:
        return f"{self.api_base_url}{self.swagger_doc_path}"

    @property
    def user1_auth(self) -> tuple[str, str]:
        return (self.user1_name, self.user1_password)

    @property
    def user2_auth(self) -> tuple[str, str]:
        return (self.user2_name, self.user2_password)


settings = Settings()
