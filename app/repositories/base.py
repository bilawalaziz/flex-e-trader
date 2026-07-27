from typing import Callable, Optional, Sequence, TypeVar, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import Insert, ClauseElement
from sqlalchemy.sql import func

ModelT = TypeVar("ModelT")


async def upsert(
    session: AsyncSession,
    model: Type[ModelT],
    values: dict,
    conflict_columns: list[str],
    update_columns: Optional[list[str]] = None,
    *,
    condition: Optional[Callable[[Insert], ClauseElement]] = None,
) -> bool:
    stmt = insert(model).values(**values)

    if update_columns is None:
        update_col_names = [
            c for c in values.keys() if c not in conflict_columns and c != "id"
        ]
    else:
        update_col_names = update_columns

    on_update = {col: getattr(stmt.excluded, col) for col in update_col_names}
    if hasattr(model, "processed_at"):
        on_update["processed_at"] = func.now()
    if condition:
        where_clause = condition(stmt)
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_=on_update,
            where=where_clause,
        )
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_=on_update,
        )

    result = await session.execute(stmt)
    return result.rowcount > 0


async def upsert_many(
    session: AsyncSession,
    model: Type[ModelT],
    values_list: Sequence[dict],
    conflict_columns: list[str],
    update_columns: Optional[list[str]] = None,
    *,
    condition: Optional[Callable[[Insert], ClauseElement]] = None,
    batch_size: int = 500,
) -> bool:
    if not values_list:
        return False

    total_rows = 0
    for i in range(0, len(values_list), batch_size):
        values_chunk = values_list[i : i + batch_size]
        stmt = insert(model).values(values_chunk)

        if update_columns is None:
            update_col_names = [
                c
                for c in values_chunk[0].keys()
                if c not in conflict_columns and c != "id"
            ]
        else:
            update_col_names = update_columns

        on_update = {col: getattr(stmt.excluded, col) for col in update_col_names}
        if hasattr(model, "processed_at"):
            on_update["processed_at"] = func.now()

        if condition:
            where_clause = condition(stmt)
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns,
                set_=on_update,
                where=where_clause,
            )
        else:
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns,
                set_=on_update,
            )

        result = await session.execute(stmt)
        total_rows += result.rowcount
    return total_rows
