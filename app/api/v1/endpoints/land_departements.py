"""Land departments listing endpoint."""

from fastapi import APIRouter

from app.api.deps import SettingsDep
from app.infrastructure.duckdb_pool import get_pool

router = APIRouter(tags=["land", "departements"])


@router.get("/departements")
async def list_available_departments(settings: SettingsDep):
    """List available departments (DuckDB files)."""
    pool = get_pool(data_dir=settings.data_dir, legacy_path=settings.duckdb_path)
    return {
        "count": len(pool.available_depts),
        "departements": pool.available_depts,
        "mode": "multi_dept" if settings.multi_dept else "legacy",
    }
