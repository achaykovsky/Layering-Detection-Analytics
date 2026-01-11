"""
API contracts module for inter-service communication.

Defines Pydantic models for all request/response DTOs with strict validation.
All models serialize datetime as ISO strings and Decimal as strings to preserve precision.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# Type aliases for literals
Side = Literal["BUY", "SELL"]
EventType = Literal["ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED"]
DetectionType = Literal["LAYERING", "WASH_TRADING"]
AlgorithmStatus = Literal["success", "failure", "timeout"]
AggregateStatus = Literal["completed", "validation_failed"]


class TransactionEventDTO(BaseModel):
    """
    Pydantic model for TransactionEvent API serialization.

    Converts datetime to ISO string and Decimal to string for JSON compatibility.
    """

    timestamp: str = Field(..., description="ISO format datetime string")
    account_id: str = Field(..., min_length=1, description="Account identifier")
    product_id: str = Field(..., min_length=1, description="Product identifier")
    side: Side = Field(..., description="Trade side: BUY or SELL")
    price: str = Field(..., description="Price as string (preserves Decimal precision)")
    quantity: int = Field(..., gt=0, description="Positive quantity")
    event_type: EventType = Field(..., description="Event type")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate timestamp is valid ISO format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid ISO datetime format: {v}") from e
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: str) -> str:
        """Validate price is a valid decimal string."""
        from decimal import InvalidOperation

        try:
            Decimal(v)
        except (ValueError, TypeError, InvalidOperation) as e:
            raise ValueError(f"Invalid decimal price: {v}") from e
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "timestamp": "2025-01-15T10:30:00",
                "account_id": "ACC001",
                "product_id": "IBM",
                "side": "BUY",
                "price": "100.50",
                "quantity": 1000,
                "event_type": "ORDER_PLACED",
            }
        }
    }


class SuspiciousSequenceDTO(BaseModel):
    """
    Pydantic model for SuspiciousSequence API serialization.

    Represents a detected suspicious trading pattern with optional fields
    that vary by detection type (LAYERING vs WASH_TRADING).
    """

    account_id: str = Field(..., min_length=1, description="Suspicious account identifier")
    product_id: str = Field(..., min_length=1, description="Product where activity detected")
    start_timestamp: str = Field(..., description="ISO format start datetime")
    end_timestamp: str = Field(..., description="ISO format end datetime")
    total_buy_qty: int = Field(..., ge=0, description="Total BUY quantity")
    total_sell_qty: int = Field(..., ge=0, description="Total SELL quantity")
    detection_type: DetectionType = Field(
        default="LAYERING", description="Detection type: LAYERING or WASH_TRADING"
    )
    side: Side | None = Field(default=None, description="Side for LAYERING detection")
    num_cancelled_orders: int | None = Field(
        default=None, ge=0, description="Cancelled orders count for LAYERING"
    )
    order_timestamps: list[str] | None = Field(
        default=None, description="ISO datetime strings for LAYERING orders"
    )
    alternation_percentage: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Alternation percentage for WASH_TRADING"
    )
    price_change_percentage: float | None = Field(
        default=None, description="Price change percentage for WASH_TRADING"
    )

    @field_validator("start_timestamp", "end_timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate timestamp is valid ISO format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid ISO datetime format: {v}") from e
        return v

    @field_validator("order_timestamps")
    @classmethod
    def validate_order_timestamps(cls, v: list[str] | None) -> list[str] | None:
        """Validate all order timestamps are valid ISO format."""
        if v is None:
            return v
        for timestamp in v:
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError as e:
                raise ValueError(f"Invalid ISO datetime format in order_timestamps: {timestamp}") from e
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "account_id": "ACC001",
                "product_id": "IBM",
                "start_timestamp": "2025-01-15T10:30:00",
                "end_timestamp": "2025-01-15T10:30:10",
                "total_buy_qty": 5000,
                "total_sell_qty": 0,
                "detection_type": "LAYERING",
                "side": "BUY",
                "num_cancelled_orders": 3,
                "order_timestamps": ["2025-01-15T10:30:00", "2025-01-15T10:30:05"],
            }
        }
    }


class AlgorithmRequest(BaseModel):
    """
    Request model for algorithm service detection endpoint.

    Sent from Orchestrator to Algorithm Services (Layering, Wash Trading).
    """

    request_id: str = Field(..., description="UUID request identifier")
    event_fingerprint: str = Field(..., description="SHA256 hexdigest of events")
    events: list[TransactionEventDTO] = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Transaction events (max 100,000 events to prevent DoS)",
    )

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Validate request_id is a valid UUID."""
        try:
            UUID(v)
        except ValueError as e:
            raise ValueError(f"Invalid UUID format: {v}") from e
        return v

    @field_validator("event_fingerprint")
    @classmethod
    def validate_event_fingerprint(cls, v: str) -> str:
        """Validate event_fingerprint is a valid SHA256 hexdigest (64 chars)."""
        if not re.match(r"^[a-f0-9]{64}$", v.lower()):
            raise ValueError(f"Invalid SHA256 hexdigest format: {v} (must be 64 hex characters)")
        return v.lower()

    model_config = {
        "json_schema_extra": {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_fingerprint": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
                "events": [],
            }
        }
    }


class AlgorithmResponse(BaseModel):
    """
    Response model from algorithm service detection endpoint.

    Returned from Algorithm Services to Orchestrator.
    """

    request_id: str = Field(..., description="UUID request identifier")
    service_name: str = Field(..., description="Service name: 'layering' or 'wash_trading'")
    status: AlgorithmStatus = Field(..., description="Processing status")
    results: list[SuspiciousSequenceDTO] | None = Field(
        default=None, description="Detected sequences (null on failure)"
    )
    error: str | None = Field(default=None, description="Error message (null on success)")
    final_status: bool = Field(
        default=True,
        description="True if service completed (no more retries), False if still retrying",
    )

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Validate request_id is a valid UUID."""
        try:
            UUID(v)
        except ValueError as e:
            raise ValueError(f"Invalid UUID format: {v}") from e
        return v

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        """Validate service_name is one of the expected values."""
        if v not in ("layering", "wash_trading"):
            raise ValueError(f"Invalid service_name: {v} (must be 'layering' or 'wash_trading')")
        return v

    @model_validator(mode="after")
    def validate_consistency(self) -> "AlgorithmResponse":
        """Validate results and error consistency with status."""
        if self.status == "success":
            if self.results is None:
                raise ValueError("results must be non-null when status is 'success'")
            if self.error is not None:
                raise ValueError("error must be null when status is 'success'")
        elif self.status in ("failure", "timeout"):
            if self.results is not None:
                raise ValueError(f"results must be null when status is '{self.status}'")
            if self.error is None:
                raise ValueError(f"error must be non-null when status is '{self.status}'")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "service_name": "layering",
                "status": "success",
                "results": [],
                "error": None,
            }
        }
    }


class AggregateRequest(BaseModel):
    """
    Request model for aggregator service aggregate endpoint.

    Sent from Orchestrator to Aggregator Service.
    """

    request_id: str = Field(..., description="UUID request identifier")
    expected_services: list[str] = Field(..., min_length=1, description="Expected service names")
    results: list[AlgorithmResponse] = Field(..., min_length=1, description="Algorithm service results")

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Validate request_id is a valid UUID."""
        try:
            UUID(v)
        except ValueError as e:
            raise ValueError(f"Invalid UUID format: {v}") from e
        return v

    @field_validator("expected_services")
    @classmethod
    def validate_expected_services(cls, v: list[str]) -> list[str]:
        """Validate expected_services contains valid service names."""
        valid_services = {"layering", "wash_trading"}
        for service in v:
            if service not in valid_services:
                raise ValueError(f"Invalid service name: {service} (must be one of {valid_services})")
        if len(v) != len(set(v)):
            raise ValueError("expected_services must contain unique service names")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "expected_services": ["layering", "wash_trading"],
                "results": [],
            }
        }
    }


class AggregateResponse(BaseModel):
    """
    Response model from aggregator service aggregate endpoint.

    Returned from Aggregator Service to Orchestrator.
    """

    status: AggregateStatus = Field(..., description="Aggregation status")
    merged_count: int = Field(..., ge=0, description="Number of merged sequences")
    failed_services: list[str] = Field(default_factory=list, description="Failed service names")
    error: str | None = Field(default=None, description="Error message (null on success)")

    @model_validator(mode="after")
    def validate_consistency(self) -> "AggregateResponse":
        """Validate error consistency with status."""
        if self.status == "completed" and self.error is not None:
            raise ValueError("error must be null when status is 'completed'")
        if self.status == "validation_failed" and self.error is None:
            raise ValueError("error must be non-null when status is 'validation_failed'")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "completed",
                "merged_count": 5,
                "failed_services": [],
                "error": None,
            }
        }
    }

