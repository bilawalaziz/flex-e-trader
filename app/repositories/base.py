# app/repositories/base.py
from typing import TypeVar, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

ModelT = TypeVar("ModelT")


async def upsert(
    session: AsyncSession,
    model: Type[ModelT],
    values: dict,
    conflict_columns: list[str],
) -> bool:
    stmt = (
        insert(model)
        .values(**values)
        .on_conflict_do_nothing(index_elements=conflict_columns)
    )
    result = await session.execute(stmt)
    return result.rowcount > 0
