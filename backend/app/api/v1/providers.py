"""CRUD API endpoints for LLM Provider, Model, and Agent Model Configuration."""

from __future__ import annotations

import time
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.error_handler import NotFoundError, ValidationErrorDetail
from app.api.schemas.provider import (
    AgentModelConfigCreate,
    AgentModelConfigDetailResponse,
    AgentModelConfigResponse,
    AgentModelConfigUpdate,
    ModelCreate,
    ModelListResponse,
    ModelResponse,
    ModelTestRequest,
    ModelTestResponse,
    ModelUpdate,
    ProviderCreate,
    ProviderDetailResponse,
    ProviderListResponse,
    ProviderResponse,
    ProviderTestRequest,
    ProviderTestResponse,
    ProviderUpdate,
)
from app.db.session import get_db
from app.services import provider_service

router = APIRouter(tags=["llm"])

# ── Provider Endpoints ──────────────────────────────────────────────────────


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
) -> ProviderListResponse:
    """List all LLM providers."""
    providers, total = await provider_service.list_providers(
        db, page=page, page_size=page_size, include_inactive=include_inactive,
    )
    pages = (total + page_size - 1) // page_size
    return ProviderListResponse(
        items=[ProviderResponse.model_validate(p) for p in providers],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.get("/providers/{provider_id}", response_model=ProviderDetailResponse)
async def get_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProviderDetailResponse:
    """Get a single provider with its models."""
    provider = await provider_service.get_provider(db, provider_id)
    if provider is None:
        raise NotFoundError(f"Provider {provider_id} not found")

    resp = ProviderDetailResponse.model_validate(provider)
    resp.models = [ModelResponse.model_validate(m) for m in (provider.models or [])]
    return resp


@router.post("/providers", response_model=ProviderResponse, status_code=201)
async def create_provider(
    body: ProviderCreate,
    db: AsyncSession = Depends(get_db),
) -> ProviderResponse:
    """Create a new LLM provider."""
    # Check slug uniqueness
    existing = await provider_service.get_provider_by_slug(db, body.slug)
    if existing:
        raise ValidationErrorDetail(f"Provider with slug '{body.slug}' already exists")

    provider = await provider_service.create_provider(db, body.model_dump())
    await db.commit()
    return ProviderResponse.model_validate(provider)


@router.post("/providers/test", response_model=ProviderTestResponse)
async def test_provider_connection(
    body: ProviderTestRequest,
) -> ProviderTestResponse:
    """Test a provider connection by calling its models endpoint."""
    url = body.api_base_url.rstrip("/") + "/models"
    headers = {"Content-Type": "application/json"}
    if body.api_key:
        headers["Authorization"] = f"Bearer {body.api_key}"

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)

        latency = int((time.monotonic() - start) * 1000)

        if response.status_code == 200:
            return ProviderTestResponse(
                success=True,
                message=f"Connected successfully ({response.status_code})",
                latency_ms=latency,
            )
        elif response.status_code == 401:
            return ProviderTestResponse(
                success=False,
                message=f"Authentication failed (401). Check your API key.",
                latency_ms=latency,
            )
        elif response.status_code == 404:
            # /models not found — the base URL itself is reachable, try a basic GET on the base
            try:
                start2 = time.monotonic()
                resp2 = await client.get(body.api_base_url.rstrip("/"), headers=headers)
                latency2 = int((time.monotonic() - start2) * 1000)
                if resp2.status_code < 500:
                    return ProviderTestResponse(
                        success=True,
                        message=f"Base URL reachable ({resp2.status_code}), but /models endpoint not found.",
                        latency_ms=latency2,
                    )
            except Exception:
                pass
            return ProviderTestResponse(
                success=False,
                message=f"Endpoint /models returned 404. Verify the base URL is correct.",
                latency_ms=latency,
            )
        else:
            return ProviderTestResponse(
                success=False,
                message=f"Unexpected response {response.status_code}. Verify the URL and credentials.",
                latency_ms=latency,
            )
    except httpx.ConnectError:
        latency = int((time.monotonic() - start) * 1000)
        return ProviderTestResponse(
            success=False,
            message=f"Cannot connect to {body.api_base_url}. Check the URL and network.",
            latency_ms=latency,
        )
    except httpx.TimeoutException:
        latency = int((time.monotonic() - start) * 1000)
        return ProviderTestResponse(
            success=False,
            message="Connection timed out after 10 seconds.",
            latency_ms=latency,
        )
    except Exception as exc:
        latency = int((time.monotonic() - start) * 1000)
        return ProviderTestResponse(
            success=False,
            message=f"Connection failed: {type(exc).__name__}",
            latency_ms=latency,
        )


@router.put("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: uuid.UUID,
    body: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProviderResponse:
    """Update an LLM provider."""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise ValidationErrorDetail("No fields provided for update.")

    provider = await provider_service.update_provider(db, provider_id, update_data)
    if provider is None:
        raise NotFoundError(f"Provider {provider_id} not found")
    await db.commit()
    return ProviderResponse.model_validate(provider)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an LLM provider and its models."""
    deleted = await provider_service.delete_provider(db, provider_id)
    if not deleted:
        raise NotFoundError(f"Provider {provider_id} not found")
    await db.commit()


# ── Model Endpoints ─────────────────────────────────────────────────────────


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    provider_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
) -> ModelListResponse:
    """List all models, optionally filtered by provider."""
    models, total = await provider_service.list_models(
        db, provider_id=provider_id, page=page, page_size=page_size,
        include_inactive=include_inactive,
    )
    pages = (total + page_size - 1) // page_size
    return ModelListResponse(
        items=[ModelResponse.model_validate(m) for m in models],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.get("/providers/{provider_id}/models", response_model=ModelListResponse)
async def list_provider_models(
    provider_id: uuid.UUID,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
) -> ModelListResponse:
    """List all models for a specific provider."""
    # Verify provider exists
    provider = await provider_service.get_provider(db, provider_id)
    if provider is None:
        raise NotFoundError(f"Provider {provider_id} not found")

    models, total = await provider_service.list_models(
        db, provider_id=provider_id, page=page, page_size=page_size,
        include_inactive=include_inactive,
    )
    pages = (total + page_size - 1) // page_size
    return ModelListResponse(
        items=[ModelResponse.model_validate(m) for m in models],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.get("/models/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ModelResponse:
    """Get a single model by ID."""
    model = await provider_service.get_model(db, model_id)
    if model is None:
        raise NotFoundError(f"Model {model_id} not found")
    return ModelResponse.model_validate(model)


@router.post("/providers/{provider_id}/models", response_model=ModelResponse, status_code=201)
async def create_model(
    provider_id: uuid.UUID,
    body: ModelCreate,
    db: AsyncSession = Depends(get_db),
) -> ModelResponse:
    """Create a new model under a provider."""
    provider = await provider_service.get_provider(db, provider_id)
    if provider is None:
        raise NotFoundError(f"Provider {provider_id} not found")

    model = await provider_service.create_model(db, provider_id, body.model_dump())
    await db.commit()
    return ModelResponse.model_validate(model)


@router.put("/models/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: uuid.UUID,
    body: ModelUpdate,
    db: AsyncSession = Depends(get_db),
) -> ModelResponse:
    """Update a model."""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise ValidationErrorDetail("No fields provided for update.")

    model = await provider_service.update_model(db, model_id, update_data)
    if model is None:
        raise NotFoundError(f"Model {model_id} not found")
    await db.commit()
    return ModelResponse.model_validate(model)


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a model."""
    deleted = await provider_service.delete_model(db, model_id)
    if not deleted:
        raise NotFoundError(f"Model {model_id} not found")
    await db.commit()


@router.post("/models/test", response_model=ModelTestResponse)
async def test_model_on_provider(
    body: ModelTestRequest,
    db: AsyncSession = Depends(get_db),
) -> ModelTestResponse:
    """Test whether a model slug exists on a provider by calling its /models endpoint."""
    provider = await provider_service.get_provider(db, body.provider_id)
    if provider is None:
        raise NotFoundError(f"Provider {body.provider_id} not found")
    if not provider.api_base_url:
        return ModelTestResponse(
            success=False,
            message="Provider has no API base URL configured.",
        )

    url = provider.api_base_url.rstrip("/") + "/models"
    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)

        latency = int((time.monotonic() - start) * 1000)

        if response.status_code != 200:
            return ModelTestResponse(
                success=False,
                message=f"Provider returned {response.status_code}. Cannot list models.",
                latency_ms=latency,
            )

        # Parse model list — handle both object-array and string-array responses
        data = response.json()
        available: list[str] = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    available.append(item)
                elif isinstance(item, dict):
                    available.append(item.get("id", "") or item.get("model", "") or "")
        elif isinstance(data, dict):
            models_data = data.get("data") or data.get("models") or []
            for item in models_data:
                if isinstance(item, str):
                    available.append(item)
                elif isinstance(item, dict):
                    available.append(item.get("id", "") or item.get("model", "") or "")

        available = [m for m in available if m]

        target_slug = body.model_slug
        found = target_slug in available

        if found:
            return ModelTestResponse(
                success=True,
                message=f"Model '{target_slug}' found on {provider.name}.",
                latency_ms=latency,
                available_models=available,
            )
        else:
            return ModelTestResponse(
                success=False,
                message=f"Model '{target_slug}' not found on {provider.name}.",
                latency_ms=latency,
                available_models=available,
            )

    except httpx.ConnectError:
        latency = int((time.monotonic() - start) * 1000)
        return ModelTestResponse(
            success=False,
            message=f"Cannot connect to {provider.api_base_url}. Check the URL and network.",
            latency_ms=latency,
        )
    except httpx.TimeoutException:
        latency = int((time.monotonic() - start) * 1000)
        return ModelTestResponse(
            success=False,
            message="Connection timed out after 10 seconds.",
            latency_ms=latency,
        )
    except Exception as exc:
        latency = int((time.monotonic() - start) * 1000)
        return ModelTestResponse(
            success=False,
            message=f"Model test failed: {type(exc).__name__}",
            latency_ms=latency,
        )


# ── Agent Model Config Endpoints ────────────────────────────────────────────


@router.get("/agents/{agent_name}/model-config", response_model=AgentModelConfigDetailResponse)
async def get_agent_model_config(
    agent_name: str,
    db: AsyncSession = Depends(get_db),
) -> AgentModelConfigDetailResponse:
    """Get the active model configuration for an agent."""
    config = await provider_service.get_agent_config(db, agent_name)
    if config is None:
        raise NotFoundError(f"No model configuration found for agent '{agent_name}'")

    resp = AgentModelConfigDetailResponse.model_validate(config)
    # Resolve provider and model names
    provider = await provider_service.get_provider(db, config.provider_id)
    model = await provider_service.get_model(db, config.model_id)
    if provider:
        resp.provider_name = provider.name
    if model:
        resp.model_name = model.name
        resp.model_slug = model.slug
    return resp


@router.put("/agents/{agent_name}/model-config", response_model=AgentModelConfigDetailResponse)
async def set_agent_model_config(
    agent_name: str,
    body: AgentModelConfigCreate,
    db: AsyncSession = Depends(get_db),
) -> AgentModelConfigDetailResponse:
    """Set or update an agent's model configuration."""
    # Validate provider and model exist
    provider = await provider_service.get_provider(db, body.provider_id)
    if provider is None:
        raise NotFoundError(f"Provider {body.provider_id} not found")
    model = await provider_service.get_model(db, body.model_id)
    if model is None:
        raise NotFoundError(f"Model {body.model_id} not found")

    config = await provider_service.set_agent_config(db, agent_name, body.model_dump())
    await db.commit()
    await db.refresh(config)

    resp = AgentModelConfigDetailResponse.model_validate(config)
    resp.provider_name = provider.name
    resp.model_name = model.name
    resp.model_slug = model.slug
    return resp


@router.patch("/agents/{agent_name}/model-config", response_model=AgentModelConfigDetailResponse)
async def update_agent_model_config(
    agent_name: str,
    body: AgentModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentModelConfigDetailResponse:
    """Partially update an agent's model configuration."""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise ValidationErrorDetail("No fields provided for update.")

    # Validate provider and model if provided
    if "provider_id" in update_data:
        provider_obj = await provider_service.get_provider(db, update_data["provider_id"])
        if provider_obj is None:
            raise NotFoundError(f"Provider {update_data['provider_id']} not found")
    if "model_id" in update_data:
        model_obj = await provider_service.get_model(db, update_data["model_id"])
        if model_obj is None:
            raise NotFoundError(f"Model {update_data['model_id']} not found")

    config = await provider_service.set_agent_config(db, agent_name, update_data)
    await db.commit()
    await db.refresh(config)

    config_provider = await provider_service.get_provider(db, config.provider_id)
    config_model = await provider_service.get_model(db, config.model_id)

    resp = AgentModelConfigDetailResponse.model_validate(config)
    if config_provider:
        resp.provider_name = config_provider.name
    if config_model:
        resp.model_name = config_model.name
        resp.model_slug = config_model.slug
    return resp


@router.delete("/agents/{agent_name}/model-config", status_code=204)
async def delete_agent_model_config(
    agent_name: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an agent's model configuration (agent will use default)."""
    deleted = await provider_service.delete_agent_config(db, agent_name)
    if not deleted:
        raise NotFoundError(f"No model configuration found for agent '{agent_name}'")
    await db.commit()
