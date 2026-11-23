"""
PostgreSQL database connector providing connection management for the application chassis

Copyright (C) 2011 - 2026 Azist, MIT License
"""

from functools import lru_cache
from typing import Callable, override
import json
import re
import ast
import copy

import asyncio
import asyncpg

from configparser import ConfigParser

from azos.ambient import Ambient
from azos.apm.log import LogStrand
from azos.chassis import AppChassis, AppComponent, ChassisDescriptorFactory, expand_var_expressions as evar
from azos.descriptor import Descriptor
from azos.exceptions import AzosError
from azos.factoryutils import knownas


CONFIG_SECTION = "pg-sql-chassis"

# Tokenizer for PostgreSQL lexical structure. Skipped constructs are matched first (leftmost wins), so
# a `$name` inside of them is never seen by the `name` alternative. Bodies use the unrolled-loop form
# `[^x]*(?:xx[^x]*)*` to avoid catastrophic backtracking on unterminated input.
_SQL_TOKEN = re.compile(
    r"""
    (?P<skip>
        --[^\n]*                                              # line comment (to EOL or EOF)
      | (?<![\w$])[eE]'[^'\\]*(?:(?:\\.|'')[^'\\]*)*'         # E'..' escape string: backslash-x and ''
      | '[^']*(?:''[^']*)*'                                   # standard string (also B'', X'', U&''): only ''
      | "[^"]*(?:""[^"]*)*"                                   # quoted identifier: only ""
      | (?<![\w$])(?P<dq>\$(?:[A-Za-z_]\w*)?\$).*?(?P=dq)     # dollar-quoted $tag$..$tag$ (tag optional)
    )
  | (?P<bcomment>/\*)                                         # block comment start, nesting handled by the loop
  | (?P<bad>(?<![\w$])[eE]'|'|"|(?<![\w$])\$(?:[A-Za-z_]\w*)?\$)  # opener of an unterminated construct
  | (?<![\w$])\$(?P<name>[A-Za-z_]\w*)                        # the actual named parameter
    """,
    re.VERBOSE | re.DOTALL,
)

_BLOCK_COMMENT_EDGE = re.compile(r"/\*|\*/")

_LOG = LogStrand("pgconnector")

# Max number of distinct SQL texts kept in the compile cache. Compiling more texts than this over the process
# lifetime means that SQL text is generated dynamically, which is an implementation error
SQL_CACHE_SIZE = 512
_sql_cache_compiles = 0

def _unterminated(sql: str, pos: int, what: str) -> AzosError:
    snippet = sql[pos:pos + 40].replace("\n", " ")
    return AzosError(
        message=f"Unterminated {what} at position {pos}: `{snippet}`",
        topic="pgconnector",
        frm="compile_named(sql)",
        src=0
    )


@lru_cache(maxsize=SQL_CACHE_SIZE)
def __compile_named(sql: str) -> tuple[str, tuple[str, ...]]:
    """
    Converts `$name` placeholders into asyncpg positional `$N` form. Returns the translated SQL
    and the ordered parameter names. Same name used many times maps to the same `$N`.
    The translated text is stable per source SQL so asyncpg per-connection prepared statement cache is reused.

    Honors PostgreSQL lexical structure: `$name` is NOT a parameter inside of `-- line comments`,
    nested `/* block /* comments */ */`, `'strings'` (`''` escape), `E'strings'` (backslash and `''` escapes),
    `"quoted identifiers"` and `$tag$dollar quoted$tag$` bodies. Also `foo$name` (identifier char before `$`)
    and positional `$1` are left as-is. Assumes `standard_conforming_strings=on` (PostgreSQL default).

    :raises AzosError: on unterminated string, quoted identifier, dollar-quote or block comment.
    """
    # This body runs on cache MISS only
    global _sql_cache_compiles

    _sql_cache_compiles += 1

    if _sql_cache_compiles > SQL_CACHE_SIZE:
        _LOG.critical(f"SQL compile is overused: {_sql_cache_compiles} times. Who is generating SQLs dynamically?")

    names: list[str] = []
    out: list[str] = []
    pos = 0

    while True:
        m = _SQL_TOKEN.search(sql, pos)
        if m is None:
            out.append(sql[pos:])
            break

        out.append(sql[pos:m.start()])

        if m.group("name") is not None:
            name = m.group("name")
            if name not in names:
                names.append(name)
            out.append(f"${names.index(name) + 1}")
            pos = m.end()
        elif m.group("bcomment") is not None:
            depth, i = 1, m.end()
            while depth:
                e = _BLOCK_COMMENT_EDGE.search(sql, i)
                if e is None:
                    raise _unterminated(sql, m.start(), "block comment")
                depth += 1 if e.group() == "/*" else -1
                i = e.end()
            out.append(sql[m.start():i])
            pos = i
        elif m.group("bad") is not None:
            tok = m.group("bad")
            what = "quoted identifier" if tok == '"' else "dollar-quoted string" if tok.endswith("$") else "string literal"
            raise _unterminated(sql, m.start(), what)
        else:  # skipped token, copy verbatim
            out.append(m.group())
            pos = m.end()

    return "".join(out), tuple(names)


def bind(sql: str, **params) -> tuple:
    """
    Binds named parameters to SQL with `$name` placeholders, returning a `(sql, *args)` tuple for asyncpg
    positional API: `await conn.execute(*bind(SQL, a=1, b=2))`. Extra params are ignored.

    #### Strings and Comments - Ignored
    This function is smart enough to ignore `$param` names in strings and comments.

    #### Provides cache abuse protection:
    you should never dynamically concatenate many different SQL statements
    because it will exhaust cache and start generating CRITICAL log failures once cache gets saturated.
    If you need SQL variability you CAN create a few SQL variations but not 100s of them as cache is capped at
    SQL_CACHE_SIZE constant (512 entries).

    :raises AzosError: if SQL can not be compiled (e.g. unterminated string/comment, not a string)
        or if SQL references a parameter which is not supplied.
    """
    try:
        text, names = __compile_named(sql)
    except AzosError:
        raise
    except Exception as e:
        raise AzosError(
            message=f"SQL compilation failed: {e.__class__.__name__}: {e}",
            topic="pgconnector",
            frm=f"bind(sql=`{str(sql)[:80]}`)",
            src=0
        ) from e

    try:
        return (text, *(params[n] for n in names))
    except KeyError as e:
        raise AzosError(
            message=f"SQL parameter `{e.args[0]}` was not supplied",
            topic="pgconnector",
            frm=f"bind(params=`{', '.join(params)}`)",
            src=0
        ) from e


class PgSqlCtreeChassisDescriptorFactory(ChassisDescriptorFactory):
    """
    Fetches application chassis descriptors by fetching the app config from PgSQL ctree
    bypassing complex ctree mechanics which rely on loaded modules.

    You have to have a running PgSQL instance and application configured under
    `/boot/app/{app_id}` path in the tree.

    Cluster boots central `gov` service using this bootloader, then subsequent services obtain full
    configuration from the `gov` service via a network call.

    ATTENTION: You MUST call this ONLY from sync application bootstrapping code (pass the instance to chassis).
    Never call it from async code path, because it will block the event loop and cause deadlocks.
    """

    async def acquire_connection(self, environment: str, config: ConfigParser) -> asyncpg.Connection:
        try:
            url = evar(config.get(CONFIG_SECTION, "url", fallback=None))

            # If no URL provided, build it from individual components
            if not url:
                database = evar(config.get(CONFIG_SECTION, "database", fallback=None))
                user = evar(config.get(CONFIG_SECTION, "user", fallback=None))
                password = evar(config.get(CONFIG_SECTION, "password", fallback=None))
                host = evar(config.get(CONFIG_SECTION, "host", fallback="127.0.0.1")) or "127.0.0.1"
                port = evar(config.get(CONFIG_SECTION, "port", fallback="5432")) or "5432"

                url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

            # Pass only DSN, avoiding parameter conflicts
            return await asyncpg.connect(dsn=url)
        except Exception as e:
            raise AzosError(
                message=f"Unable to establish PgSql connection to ctree db as specified in `[{CONFIG_SECTION}]`",
                topic="pgconnector",
                frm=f"acquire_connection(env=`{environment}`, db=`{config.get(CONFIG_SECTION, 'database', fallback='?')}`)",
                src=0
            ) from e


    async def doWork(self,
                     instance_id: str,
                     entry_point_path: str,
                     app_id: str,
                     environment: str,
                     host: str,
                     config: ConfigParser) -> "Descriptor":

        cnn = await self.acquire_connection(environment, config)
        try:
            # we will read the config using schema in ../sky/ctree.pg.sql

            # we need to fetch the following paths: in sequence
            # `/` root, then `/boot`, `/boot/app`, `/boot/app/{app_id}`
            # so we need to do 4 reads, all AS OF UTC NOW (at the time of call).
            # we then need to override `config` Descriptor from top to bottom and return the final Descriptor.
            # You can hint how it is done from ../sky/ctree.py


            # Get current time as UTC timestamp for "as of" queries
            # Note: using naive datetime to match PostgreSQL 'timestamp' type (not 'timestamptz')
            asof_utc = Ambient.utc_now()

            # Build the list of paths to fetch in order
            paths = [
                "/",
                "/boot",
                "/boot/app",
                f"/boot/app/{app_id}"
            ]

            # Start with empty descriptor
            result = Descriptor({})

            # Query each path and override the result
            for path in paths:
                query = """
                    SELECT "config"
                    FROM "tbl_ctree"
                    WHERE "path" = $1
                        AND "asof_utc" <= $2
                        AND "ver_state" != 'd'
                    ORDER BY "asof_utc" DESC
                    LIMIT 1
                """

                row = await cnn.fetchrow(query, path, asof_utc)

                if not row:
                    raise AzosError(
                        message=f"Configuration node not found in ctree",
                        topic="pgconnector",
                        frm=f"doWork(path=`{path}`)",
                        src=1
                    )

                config_data = row["config"]
                if not config_data:
                    raise AzosError(
                        message=f"Configuration data is empty for path",
                        topic="pgconnector",
                        frm=f"doWork(path=`{path}`)",
                        src=2
                    )

                if isinstance(config_data, str):
                    config_data = json.loads(config_data)

                # Create descriptor from fetched config and override
                override_descriptor = Descriptor(config_data)
                result = result.override_by(override_descriptor)

            return result
        finally:
            await cnn.close()


    @override
    def __call__(self,
                instance_id: str,
                entry_point_path: str,
                app_id: str,
                environment: str,
                host: str,
                config: ConfigParser) -> "Descriptor":

        try:
            result = asyncio.run(self.doWork(instance_id,
                                             entry_point_path,
                                             app_id,
                                             environment,
                                             host,
                                             config))
            return result
        except Exception as e:
            raise AzosError(
                message=f"!!!Catastrophic failure!!!: \n"
                        f"PgSqlCtreeChassisDescriptorFactory was not able to obtain descriptor to bootload chassis \n"
                        f"Inspect the inner error for details \n"
                        f"Inner error: \n     {str(e)}",
                topic="pgconnector",
                frm=f"__call__(app_id=`{app_id}`, env=`{environment}`, host=`{host}`)",
                src=0
            ) from e


@knownas("PgConnector")
class PgConnector(AppComponent):
    """
    PostgreSQL database connector providing connection management for the application chassis.

    Warning: this is an ASYNC context manager app component and it needs to be enter/exit-ed accordingly:
    entered after construction and existed before app destruction. This component is for a single event
    loop use, not multi-threading!!!
    """

    def __init__(self, chassis: AppChassis, director: AppComponent | None, config: Descriptor):
        super().__init__(chassis, director=director)

        self._cfg = config.clone()
        self._pools = {}
        self._log = LogStrand(self.__class__.__name__)
        self._active = False


    @override
    def _dispose(self):
        alive = len(self._pools)
        if alive > 0:
            # Log Memory leak error
            self._log.critical(f"Implementation error: disposing with {alive} pools!!! Must have called __aexit()__ to finalize before dispose")

        self._active = False
        super()._dispose()


    async def __aenter__(self):

        self.ensure_not_disposed()
        if self._active:
            raise RuntimeError("__aenter()__ on already open PgConnector")

        pools = [Descriptor(map, self.chassis, self._cfg, f"/[name={map.get("name")}]",) for map in self._cfg.as_required_list("pools")]

        try:
            for pool_config in pools:
                name = (pool_config.as_str("name") or "").strip().lower()

                if name == "":
                    raise ValueError(f"Connection pool name is required in {self._cfg.scope_path}")

                if name in self._pools:
                    raise ValueError(f"Duplicate connection pool name: {name}")

                pool = await self._create_pool(name, pool_config)
                self._pools[name] = pool
        except Exception:
            await self._close_all_pools()
            raise


        self._active = True
        return self


    async def _close_all_pools(self):
        """
        Internal helper to safely close all established connection pools.
        """
        for name, pool in list(self._pools.items()):
            try:
                await self._close_pool(name, pool)
            except Exception:
                # suppress exceptions during teardown to continue closing others
                self._log.error("Pool close leaked", exc_info=True)
        self._pools.clear()


    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._active = False
        await self._close_all_pools()


    async def _init_connection(self, conn: asyncpg.Connection):
        """
        Initialize a new connection with any required settings.
        Override this method to customize connection initialization (e.g., set session variables).
        """
        # Example: await conn.execute("SET search_path TO my_schema")

        # Register the codec for jsonb (and/or 'json') columns
        await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


    async def _create_pool(self, name: str, pool_config: Descriptor) -> asyncpg.pool.Pool:
        """
        Create a new connection pool for the given name and configuration.
        Override this method to use a custom connection pool creation logic if needed.

        :param name: The name of the connection pool.
        :param pool_config: The configuration descriptor for the pool.
        :return: An asyncpg.pool.Pool instance.
        """
        return await asyncpg.create_pool(dsn=pool_config.as_str("dsn"),
                                         min_size=pool_config.as_int("min-size") or 0,
                                         max_size=pool_config.as_int("max-size") or 2,
                                         timeout=pool_config.as_float("timeout") or 10.5,
                                         max_queries=pool_config.as_int("max-queries") or 500,
                                         max_inactive_connection_lifetime=pool_config.as_float("inactive-lifetime") or 45.5,
                                         init=self._init_connection)


    async def _close_pool(self, name: str, pool: asyncpg.pool.Pool):
        """
        Close an existing connection pool.
        Override this method to use a custom connection pool teardown logic if needed (e.g. for GCP Connector).

        :param name: The name of the connection pool.
        :param pool: The asyncpg.pool.Pool instance.
        """
        await pool.close()


    def get_connection(self, name: str) -> asyncpg.pool.PoolAcquireContext:
        """
        Retrieve a connection from the connection pool by name.
        Use it and release it:

        ```python
        async with pg_connector.get_connection("my_pool") as conn:
            # Use the connection
            cnt = await conn.fetchval("SELECT COUNT(*) FROM tbl_doctor")
            print(f"Doctor count: {cnt}")
        ```

        :param name: The name of the connection pool.
        :return: An async context manager resolving to an active asyncpg.Connection instance.
        :raises ValueError: If no connection pool is found for the given name.
        """

        if not self._active:
            raise RuntimeError("get_connection() on closed PgConnector")

        pool = self._pools.get(name, None)

        if pool is None:
            raise ValueError(f"No connection pool named: `{name}`")

        return pool.acquire()


class _FoldSigns(ast.NodeTransformer):
    """Folds unary signs applied to numeric literals, e.g. `-5`, into constants"""

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        operand = node.operand
        if isinstance(node.op, (ast.USub, ast.UAdd)) and isinstance(operand, ast.Constant):
            value = operand.value
            if type(value) is int or type(value) is float:
                return ast.copy_location(ast.Constant(-value if isinstance(node.op, ast.USub) else value), node)
        return node


class PgASTXlat(ast.NodeVisitor):
    """
    Translates a Python AST expression into a SQL filter expression.
    Use `PgASTXlat().from_string(filter_str)` to get a parameterized SQL string and a list of query
    arguments.

    Supported: `==`, `!=`, `>`, `>=`, `<`, `<=` (including chained), `in`/`not in` against a list/tuple/set
    of constants, `and`, `or`, `not`, and parentheses. Anything else raises `AzosError`. Each comparison
    must reference at least one column.

    `limits` is an optional list of allowed column names; `None` or empty allows any column.
    `convert` is an optional `(xlat, column, value) -> object` callable which converts the constant
    compared with a column into the query argument. Alternatively, override `do_convert()`.
    """

    SQL_OPS = {
        ast.Eq: "=",
        ast.NotEq: "!=",
        ast.Gt: ">",
        ast.GtE: ">=",
        ast.Lt: "<",
        ast.LtE: "<="
    }

    def __init__(self,
                 limits: list[str] | None = None,
                 convert: Callable[["PgASTXlat", str, object], object] | None = None):
        self.params = []
        self.converted: dict[int, object] = {}
        self.limits = frozenset(limits) if limits else None
        self.convert = convert

    def do_convert(self, column: str, value: object) -> object:
        """
        Override to convert/validate the constant `value` compared with `column`. Default calls
        the `convert` callable, if any, otherwise returns the value as-is. Raise to reject.
        """
        return self.convert(self, column, value) if self.convert is not None else value

    def from_string(self, filter: str) -> tuple[str, list]:
        try:
            filter_expr = ast.parse(filter, mode='eval')
        except (SyntaxError, ValueError) as e:
            raise self.__fail(f"Invalid filter expression: {e}") from e
        return self.from_expression(filter_expr)

    def from_expression(self, expression: ast.Expression) -> tuple[str, list]:
        """
        Returns a parameterized SQL string and a list of query arguments.
        """
        self.params = []
        self.converted = {}
        expression = _FoldSigns().visit(copy.deepcopy(expression))
        sql_string = self.visit(expression)
        return sql_string, self.params

    def from_order_string(self, order: str | None) -> str | None:
        """
        Translates an order by expression `field1 asc, field2 desc` into a SQL ORDER BY clause body
        (without the `ORDER BY` keyword), e.g. `"field1" ASC, "field2" DESC`. Direction is optional and
        defaults to `ASC`. Returns `None` if `order` is `None` or blank. Columns are checked against `limits`
        (if any). Raises `AzosError` with 422 status for invalid expressions or disallowed columns.
        """
        if order is None or not order.strip():
            return None

        items = []
        for part in order.split(","):
            tokens = part.split()
            if not 1 <= len(tokens) <= 2:
                raise self.__fail(f"Invalid order by item: `{part.strip()}`")

            column = tokens[0]
            # Column is always quoted, and Python identifiers cannot contain quotes
            if not column.isidentifier():
                raise self.__fail(f"Invalid order by column: `{column}`")
            if self.limits is not None and column not in self.limits:
                raise self.__fail(f"Column `{column}` is not allowed in order by")

            direction = tokens[1].upper() if len(tokens) == 2 else "ASC"
            if direction not in ("ASC", "DESC"):
                raise self.__fail(f"Invalid order by direction: `{tokens[1]}`")
            items.append(f'"{column}" {direction}')

        return ", ".join(items)

    def __fail(self, msg: str, node: ast.AST | None = None) -> AzosError:
        return AzosError(
            message=msg,
            topic="pgconnector",
            frm=f"PgASTXlat(`{type(node).__name__ if node is not None else ''}`)",
            src=400,
            status_code=422
        )

    @override
    def generic_visit(self, node: ast.AST):
        raise self.__fail(f"Unsupported filter expression element: `{type(node).__name__}`", node)

    def __predicate(self, node: ast.AST) -> str:
        if not isinstance(node, (ast.Compare, ast.BoolOp, ast.UnaryOp)):
            raise self.__fail("Filter must be a comparison or a logical combination of comparisons", node)
        return self.visit(node)

    def visit_Expression(self, node: ast.Expression) -> str:
        return self.__predicate(node.body)

    def visit_BoolOp(self, node: ast.BoolOp) -> str:
        sql_op = "AND" if isinstance(node.op, ast.And) else "OR"
        return "(" + f" {sql_op} ".join(self.__predicate(v) for v in node.values) + ")"

    def visit_UnaryOp(self, node: ast.UnaryOp) -> str:
        if not isinstance(node.op, ast.Not):
            raise self.__fail(f"Unsupported unary operator: `{type(node.op).__name__}`", node)
        return f"(NOT {self.__predicate(node.operand)})"

    def visit_Name(self, node: ast.Name) -> str:
        # Name is a column identifier; always quoted, and Python identifiers cannot contain quotes
        self.__check_column(node)
        return f'"{node.id}"'

    def __check_column(self, node: ast.Name) -> None:
        if self.limits is not None and node.id not in self.limits:
            raise self.__fail(f"Column `{node.id}` is not allowed in filter", node)

    def visit_Constant(self, node: ast.Constant) -> str:
        self.params.append(self.converted.get(id(node), node.value))
        return f"${len(self.params)}"

    def __convert_pair(self, a: ast.AST, b: ast.AST) -> None:
        """If `a` is a column and `b` is a constant, converts the constant for that column."""
        if isinstance(a, ast.Name) and isinstance(b, ast.Constant):
            self.__check_column(a)
            self.converted[id(b)] = self.do_convert(a.id, b.value)

    def __in_list(self, column: ast.AST, values: ast.AST, negate: bool) -> str:
        if not isinstance(column, ast.Name):
            raise self.__fail("Left side of `in` must be a column", column)
        if not isinstance(values, (ast.List, ast.Tuple, ast.Set)) or not values.elts:
            raise self.__fail("Right side of `in` must be a non-empty list of constants", values)
        constants = [e for e in values.elts if isinstance(e, ast.Constant) and e.value is not None]
        if len(constants) != len(values.elts):
            raise self.__fail("`in` list may only contain non-null constants", values)

        sql_column = self.visit(column)
        placeholders = []
        for e in constants:
            self.params.append(self.do_convert(column.id, e.value))
            placeholders.append(f"${len(self.params)}")
        return f"{sql_column} {'NOT IN' if negate else 'IN'} ({', '.join(placeholders)})"

    def visit_Compare(self, node: ast.Compare) -> str:
        """
        Translates `=`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `not in` comparisons. Chained comparisons `a < b <= c`
        become `(a < b AND b <= c)`. Comparing with `None` using `==`/`!=` yields `IS NULL`/`IS NOT NULL`.
        """
        operands = [node.left, *node.comparators]
        parts = []
        for i, op in enumerate(node.ops):
            if isinstance(op, (ast.In, ast.NotIn)):
                parts.append(self.__in_list(operands[i], operands[i + 1], isinstance(op, ast.NotIn)))
                continue

            sql_op = self.SQL_OPS.get(type(op))
            if sql_op is None:
                raise self.__fail(f"Unsupported comparison operator: `{type(op).__name__}`", node)

            left, right = operands[i], operands[i + 1]
            if not isinstance(left, ast.Name) and not isinstance(right, ast.Name):
                raise self.__fail("Comparison must reference at least one column", node)

            is_null_left = isinstance(left, ast.Constant) and left.value is None
            is_null_right = isinstance(right, ast.Constant) and right.value is None
            if is_null_left or is_null_right:
                if not isinstance(op, (ast.Eq, ast.NotEq)):
                    raise self.__fail("`None` may only be compared using `==` or `!=`", node)
                null_op = "IS NULL" if isinstance(op, ast.Eq) else "IS NOT NULL"
                parts.append(f"{self.visit(right if is_null_left else left)} {null_op}")
            else:
                self.__convert_pair(left, right)
                self.__convert_pair(right, left)
                parts.append(f"{self.visit(left)} {sql_op} {self.visit(right)}")

        return parts[0] if len(parts) == 1 else f"({' AND '.join(parts)})"
