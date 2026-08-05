from dataclasses import dataclass

from django.core.paginator import Paginator


@dataclass(frozen=True)
class SortState:
    field: str
    direction: str
    sort_param: str = "sort"
    direction_param: str = "direction"
    page_param: str = "page"


@dataclass(frozen=True)
class PaginationState:
    page_param: str = "page"


def _sortable_value(value):
    if isinstance(value, str):
        return value.casefold()
    return value


def sort_and_paginate(
    request,
    rows,
    *,
    allowed_sorts,
    default_sort,
    default_direction="asc",
    per_page=25,
    prefix="",
):
    """Safely sort an already tenant-scoped result set and paginate it."""
    sort_param = f"{prefix}sort" if prefix else "sort"
    direction_param = f"{prefix}direction" if prefix else "direction"
    page_param = f"{prefix}page" if prefix else "page"
    field = request.GET.get(sort_param, default_sort)
    if field not in allowed_sorts:
        field = default_sort
    direction = request.GET.get(direction_param, default_direction)
    if direction not in {"asc", "desc"}:
        direction = default_direction
    accessor = allowed_sorts[field]
    if not callable(accessor):
        accessor = lambda row, key=accessor: row.get(key)

    populated = []
    missing = []
    for row in rows:
        value = accessor(row)
        (missing if value is None else populated).append((value, row))
    populated.sort(
        key=lambda pair: _sortable_value(pair[0]),
        reverse=direction == "desc",
    )
    ordered_rows = [row for _, row in populated] + [row for _, row in missing]
    page_obj = Paginator(ordered_rows, per_page).get_page(request.GET.get(page_param))
    return (
        page_obj,
        SortState(field, direction, sort_param, direction_param, page_param),
        PaginationState(page_param),
    )
