"""Connection pool and user-scoped transactions (design D-2)."""

import json
from contextlib import contextmanager
from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings


@lru_cache
def pool() -> ConnectionPool:
    url = get_settings().database_url
    if not url:  # empty conninfo silently falls back to the local unix socket
        raise RuntimeError("DATABASE_URL is not set")
    # prepare_threshold=None: Supavisor transaction mode does not support prepared statements
    return ConnectionPool(
        url,
        min_size=1,
        max_size=5,
        kwargs={"prepare_threshold": None, "row_factory": dict_row},
        open=True,
    )


@contextmanager
def user_tx(claims: dict):
    """One transaction executed as `authenticated` with the caller's claims -> RLS applies."""
    with pool().connection() as conn:
        conn.execute("set local role authenticated")
        conn.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
        conn.execute("set local statement_timeout = '5s'")
        yield conn


@contextmanager
def service_tx():
    """Transaction as isobath_api itself. It has no table grants; only whitelisted functions."""
    with pool().connection() as conn:
        conn.execute("set local statement_timeout = '5s'")
        yield conn
