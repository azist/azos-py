"""
Provides Filtering, paging and sorting contract

Copyright (C) 2020 - 2026 Azist, MIT License
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


MAX_CLAUSE_LENGTH: int = 8 * 1024 #characters

MAX_PAGING_OFFSET: int =   10_000 # records
"""All databases handle offset/limit inefficiently due to the need to pre-process all rows.
One should never scroll a large dataset only via offset/limit. Use different rejection clause instead
to use server-side indexing
"""

MAX_PAGING_LIMIT: int =     5_000 # records
"""All databases handle offset/limit inefficiently due to the need to pre-process all rows.
One should never scroll a large dataset only via offset/limit. Use different rejection clause instead
to use server-side indexing
"""


class Filter(BaseModel):
    """
    Data filters represent a tuple of filter expressions, paging offset and limit, and order by clause.
    You submit such object for execution to the server (e.g. via FastAPI call)
    Usage of this class is the data contract which signifies the intent.
    You can derive from this class to include customized complex filters with dedicated fields
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    select: Annotated[str | None, Field(min_length=1, max_length=MAX_CLAUSE_LENGTH)] = None
    """Optional projection clause in the form `field1, field2`. Not all providers support it and most filters ignore it"""

    where: Annotated[str | None, Field(min_length=1, max_length=MAX_CLAUSE_LENGTH)] = None
    """Optional rejection clause - a filter expression, processed using AST"""

    paging_offset: Annotated[int, Field(ge=0, le=MAX_PAGING_OFFSET)] = 0
    """Filtered result set offset, 0-based, for paging"""

    paging_limit: Annotated[int, Field(ge=0, le=MAX_PAGING_LIMIT)] = 50
    """Filtered result set limit, for paging"""

    order: Annotated[str | None, Field(min_length=1, max_length=MAX_CLAUSE_LENGTH)] = None
    """
    Order by expression in the form of `field1 asc, field2 desc`.
    Your concrete filter handler may not support this expression as order may be dictated by filter business logic,
    for example while searching for customers by their names the data comes up sorted by customer last names and recency
    """
