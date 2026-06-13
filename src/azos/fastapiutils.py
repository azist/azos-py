"""FastAPI integration helpers for building opinionated app configurations"""

import sys
from pathlib import Path
from typing import Annotated, Tuple, List, TypeVar, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, APIRouter
from starlette.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

import uvicorn

from azos.oop import free
from azos.chassis import AppChassis, Injector
from azos.apm.log import LogStrand


CONFIG_SERVER_SECTION = "server"
"""Default section name in config for FastAPI server settings"""


def get_chassis(request: Request) -> AppChassis:
    """Helper to get chassis from FastAPI request context"""
    return request.app.state.chassis


ChassisDependency = Annotated[AppChassis, Depends(get_chassis)]
"""Annotate FastAPI methods with ChassisDependency to get chassis instance injected from request context"""


T = TypeVar('T')

def inject(t: type[T], name: str | None = None) -> Any:
    """Helper to inject dependency from chassis Injector for FastAPI action parameters"""
    return Annotated[t, Depends(Injector(t, name))]


def fastapi_builder(chassis: AppChassis, routers: List[APIRouter] | None = None, **other_kwargs) -> Tuple[LogStrand, FastAPI]:
    """
    Handles boilerplate FastAPI app creation and config including OpenTelemetry instrumentation.
    Returns a tuple of (LogStrand, FastAPI) for use in app setup.
    """

    log = LogStrand("app.setup", rel="self")
    log.info("Starting FastAPI app setup:")

    fa_deps = [] # dependencies

    # Ingress Security Middleware
    # ===============================
    # ===============================


    @asynccontextmanager
    async def fastapi_lifespan(faa: FastAPI):
        faa.state.chassi = chassis # Bind
        yield
        faa.state.chassis = AppChassis.get_default_instance() # Unbind

    # FastAPI App Creation
    app = FastAPI(dependencies=fa_deps, lifespan=fastapi_lifespan, **other_kwargs)
    log.debug("  * FastAPI(deps)")

    # Rate Limiter Middleware
    # ===============================
    # ===============================

    if routers:
        for router in routers:
            app.include_router(router)
        log.debug(f"  * Included {len(routers)} routers")

    FastAPIInstrumentor.instrument_app(app)
    log.debug("  * OTEL added")


    # @app.exception_handler(PermissioError)
    # async def permission_error_handler(request: Request, exc: PermissionError):
    #     return JSONResponse({"detail": str(exc)}, status_code=403)

    return log, app


def fastapi_main(chassis: AppChassis, log: LogStrand, app: FastAPI) -> None:
    log = LogStrand("app.srv", rel=log.strand_id)
    log.info("Starting uvicorn server ..")

    try:
        cfg_host = chassis.config.get(CONFIG_SERVER_SECTION, "host", fallback="0.0.0.0")
        cfg_port = chassis.config.getint(CONFIG_SERVER_SECTION, "port", fallback=8080)
        cfg_workers = chassis.config.getint(CONFIG_SERVER_SECTION, "workers", fallback=0)
        log.info(f"Binding uvicorn", extra={"h": cfg_host, "p": cfg_port, "w": cfg_workers})

        if cfg_workers > 1:
            ep = Path(chassis.entry_point_path)
            uvicorn.run(
                f"{ep.stem}:app",
                host=cfg_host,
                port=cfg_port,
                reload=False,
                log_config=None,
                workers=cfg_workers)
        else:
            uvicorn.run(
                app,
                host=cfg_host,
                port=cfg_port,
                reload=False,
                log_config=None)

    except Exception as e:
        log.critical(f"Server start failure: {e.__class__.__name__}", exc_info=True)
        sys.exit(2)

    log.info("...Uvicorn server exited")
    free(chassis) # Dispose chassis and all its resources
    log.info("App exiting normally. This is the last message.")
