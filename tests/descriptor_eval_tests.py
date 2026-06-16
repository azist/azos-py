"""
Tests for Descriptor evaluation against a deep, realistic application configuration.

The config has the following top-level sections:
  - app       : application identity and runtime settings
  - paths     : filesystem root paths referenced by other sections via $(…) variables
  - log       : structured logging configuration with multiple named sinks;
                  sink file-path values reference the 'paths' section through variable expansion
  - db-stores : data-store configurations for MongoDB, MS SQL Server, and Oracle;
                  each store carries its own connect string, fetch-by, null-treatment and
                  driver-specific options sub-section

Variable expansion:
  Log sink paths are expressed as  "$(paths/logs)/filename.log" so that relocating
  the logging directory requires only a single change in the 'paths' section.
  To resolve cross-section variables the sink Descriptor is created with
  scope= pointing at the root Descriptor.
"""

import pytest
from azos.chassis import ConfigError
from azos.descriptor import Descriptor


# ---------------------------------------------------------------------------
# Canonical deep config used by all tests in this module
# ---------------------------------------------------------------------------

def make_config() -> dict:
    """Return a fresh deep application-config dictionary."""
    return {
        # ------------------------------------------------------------------
        # app — identity and basic runtime knobs
        # ------------------------------------------------------------------
        "app": {
            "id":          "warehouse-svc",
            "description": "Warehouse management back-end service",
            "version":     "3.7.1",
            "environment": "production",
            "debug":       False,
            "max-workers": 16,
            "timezone":    "UTC",
        },

        # ------------------------------------------------------------------
        # paths — canonical filesystem roots; used via $(paths/…) variables
        #         throughout the rest of the config so that only this section
        #         needs to change when the deployment layout is adjusted
        # ------------------------------------------------------------------
        "paths": {
            "root":   "/srv/warehouse",
            "logs":   "/srv/warehouse/logs",
            "data":   "/srv/warehouse/data",
            "temp":   "/tmp/warehouse",
            "backup": "/srv/warehouse/backup",
        },

        # ------------------------------------------------------------------
        # uris — server-level network addresses for all data stores.
        #         Connect strings in 'db-stores' reference these via $(uris/…)
        #         so that endpoint changes need only one place to be edited.
        # ------------------------------------------------------------------
        "uris": {
            "mongo-primary":   "mongo1.corp:27017,mongo2.corp:27017",
            "mongo-archive":   "mongo-arc.corp:27017",
            "mssql-crm":       "sql-crm.corp,1433",
            "oracle-erp-host": "ora-erp.corp",
            "oracle-erp-port": 1521,
        },

        # ------------------------------------------------------------------
        # log — global log settings plus a list of named sinks.
        #        Sink 'path' values deliberately use $(paths/logs) so that
        #        they exercise cross-section variable resolution.
        # ------------------------------------------------------------------
        "log": {
            "min-level":   "INFO",
            "buffer-size": 8192,
            "async":       True,
            "sinks": [
                {
                    "name":      "app-file",
                    "type":      "file",
                    "path":      "$(paths/logs)/app.log",
                    "max-size":  "100mb",
                    "rotate":    True,
                    "keep":      7,
                    "min-level": "INFO",
                },
                {
                    "name":      "error-file",
                    "type":      "file",
                    "path":      "$(paths/logs)/error.log",
                    "max-size":  "50mb",
                    "rotate":    True,
                    "keep":      30,
                    "min-level": "ERROR",
                },
                {
                    "name":      "audit-file",
                    "type":      "file",
                    "path":      "$(paths/logs)/audit.log",
                    "max-size":  "200mb",
                    "rotate":    True,
                    "keep":      365,
                    "min-level": "INFO",
                },
                {
                    "name":      "structured-json",
                    "type":      "file",
                    "path":      "$(paths/logs)/structured.json.log",
                    "format":    "json",
                    "max-size":  "500mb",
                    "rotate":    True,
                    "keep":      14,
                    "min-level": "DEBUG",
                },
                {
                    "name":      "console",
                    "type":      "console",
                    "colorize":  False,
                    "min-level": "WARNING",
                },
            ],
        },

        # ------------------------------------------------------------------
        # db-stores — one entry per logical data store.
        #   Each store has:
        #     connect       — driver-specific connection string
        #     fetch-by      — default page / batch size
        #     null-treatment— how to handle SQL/BSON nulls:
        #                       "preserve" → keep as Python None
        #                       "omit"     → exclude key from result dict
        #                       "dbnull"   → use a sentinel DbNull object
        #     options       — driver-specific key/value knobs
        # ------------------------------------------------------------------
        "db-stores": {
            "default-timeout-ms":  5000,
            "default-fetch-by":    250,
            "default-null-treatment": "preserve",
            "stores": [
                # ── MongoDB primary ─────────────────────────────────────
                {
                    "name":          "mongo-primary",
                    "type":          "mongodb",
                    "connect":       "mongodb://$(uris/mongo-primary)/warehousedb?replicaSet=rs0",
                    "auth-db":       "admin",
                    "fetch-by":      500,
                    "null-treatment": "omit",
                    "options": {
                        "tls":              True,
                        "tls-ca-file":      "/etc/ssl/certs/corp-ca.pem",
                        "auth-mechanism":   "SCRAM-SHA-256",
                        "connect-timeout-ms": 3000,
                        "server-selection-timeout-ms": 5000,
                        "max-pool-size":    50,
                    },
                },
                # ── MongoDB archive (read-heavy, secondary preferred) ───
                {
                    "name":          "mongo-archive",
                    "type":          "mongodb",
                    "connect":       "mongodb://$(uris/mongo-archive)/archivedb",
                    "auth-db":       "admin",
                    "fetch-by":      1000,
                    "null-treatment": "preserve",
                    "options": {
                        "tls":              False,
                        "read-preference":  "secondaryPreferred",
                        "max-staleness-seconds": 120,
                        "max-pool-size":    20,
                    },
                },
                # ── MS SQL Server CRM ──────────────────────────────────
                {
                    "name":          "mssql-crm",
                    "type":          "mssql",
                    "connect":       "Server=$(uris/mssql-crm);Database=CRM;Encrypt=True;TrustServerCertificate=False;ApplicationName=warehouse-svc",
                    "schema":        "dbo",
                    "fetch-by":      200,
                    "null-treatment": "dbnull",
                    "options": {
                        "connection-timeout-sec":  30,
                        "command-timeout-sec":     120,
                        "multi-subnet-failover":   True,
                        "mars":                    False,
                        "min-pool-size":           2,
                        "max-pool-size":           20,
                    },
                },
                # ── Oracle ERP ─────────────────────────────────────────
                {
                    "name":          "oracle-erp",
                    "type":          "oracle",
                    "connect":       "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=$(uris/oracle-erp-host))(PORT=$(uris/oracle-erp-port)))(CONNECT_DATA=(SERVICE_NAME=ERPPRD)))",
                    "user":          "erp_ro",
                    "schema":        "ERP",
                    "fetch-by":      100,
                    "null-treatment": "preserve",
                    "options": {
                        "statement-cache-size": 50,
                        "ha-events":            True,
                        "load-balancing":       True,
                        "connection-timeout-sec": 15,
                        "min-pool-size":        1,
                        "max-pool-size":        10,
                    },
                },
            ],
        },
    }


@pytest.fixture
def cfg() -> Descriptor:
    """Root descriptor wrapping the full application config."""
    return Descriptor(make_config())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def store_desc(root: Descriptor, name: str) -> Descriptor:
    """
    Return a Descriptor for the named db-store entry, scoped to the root so
    that $(uris/…) variable expressions inside the store resolve against the
    full config tree.
    """
    ok, data = root.try_navigate(f"db-stores/stores/$name={name}")
    assert ok, f"store '{name}' not found in config"
    return Descriptor(data, scope=root)


def sink_desc(root: Descriptor, name: str) -> Descriptor:
    """
    Return a Descriptor for the named log sink, scoped to the root so that
    $(paths/…) variable expressions inside the sink resolve correctly.
    """
    ok, data = root.try_navigate(f"log/sinks/$name={name}")
    assert ok, f"log sink '{name}' not found in config"
    return Descriptor(data, scope=root)


# ===========================================================================
# 1.  App section — plain scalar reads, no variable expansion needed
# ===========================================================================

class TestAppSection:
    def test_app_id(self, cfg):
        """app/id is read back as a string."""
        assert cfg.as_str("app/id") == "warehouse-svc"

    def test_app_version(self, cfg):
        """app/version is present and correct."""
        assert cfg.as_str("app/version") == "3.7.1"

    def test_app_debug_is_false(self, cfg):
        """app/debug boolean False is preserved."""
        assert cfg.as_bool("app/debug") is False

    def test_app_max_workers(self, cfg):
        """app/max-workers integer returned correctly."""
        assert cfg.as_int("app/max-workers") == 16

    def test_app_environment(self, cfg):
        """app/environment string returned correctly."""
        assert cfg.as_str("app/environment") == "production"


# ===========================================================================
# 2.  Paths section — basis for variable expansion in other sections
# ===========================================================================

class TestPathsSection:
    def test_logs_path(self, cfg):
        assert cfg.as_str("paths/logs") == "/srv/warehouse/logs"

    def test_data_path(self, cfg):
        assert cfg.as_str("paths/data") == "/srv/warehouse/data"

    def test_temp_path(self, cfg):
        assert cfg.as_str("paths/temp") == "/tmp/warehouse"

    def test_backup_path(self, cfg):
        assert cfg.as_str("paths/backup") == "/srv/warehouse/backup"


# ===========================================================================
# 3.  URIs section — raw server address values
# ===========================================================================

class TestUrisSection:
    def test_mongo_primary_uri(self, cfg):
        assert cfg.as_str("uris/mongo-primary") == "mongo1.corp:27017,mongo2.corp:27017"

    def test_mongo_archive_uri(self, cfg):
        assert cfg.as_str("uris/mongo-archive") == "mongo-arc.corp:27017"

    def test_mssql_crm_uri(self, cfg):
        assert cfg.as_str("uris/mssql-crm") == "sql-crm.corp,1433"

    def test_oracle_erp_host(self, cfg):
        assert cfg.as_str("uris/oracle-erp-host") == "ora-erp.corp"

    def test_oracle_erp_port(self, cfg):
        assert cfg.as_int("uris/oracle-erp-port") == 1521


# ===========================================================================
# 4.  Log sinks — per-sink Descriptors scoped to root for $(paths/…) expansion
# ===========================================================================

class TestLogSinks:
    def test_sink_count(self, cfg):
        """There are exactly five configured sinks."""
        ok, sinks = cfg.try_navigate("log/sinks")
        assert ok and len(sinks) == 5

    def test_app_file_sink_path_expands(self, cfg):
        """app-file sink: $(paths/logs) is resolved to the concrete filesystem path."""
        s = sink_desc(cfg, "app-file")
        assert s.as_str("path") == "/srv/warehouse/logs/app.log"

    def test_error_file_sink_path_expands(self, cfg):
        """error-file sink: $(paths/logs) resolves correctly."""
        s = sink_desc(cfg, "error-file")
        assert s.as_str("path") == "/srv/warehouse/logs/error.log"

    def test_audit_file_sink_path_expands(self, cfg):
        """audit-file sink: $(paths/logs) resolves correctly."""
        s = sink_desc(cfg, "audit-file")
        assert s.as_str("path") == "/srv/warehouse/logs/audit.log"

    def test_structured_json_sink_path_expands(self, cfg):
        """structured-json sink: $(paths/logs) resolves correctly."""
        s = sink_desc(cfg, "structured-json")
        assert s.as_str("path") == "/srv/warehouse/logs/structured.json.log"

    def test_structured_json_sink_format(self, cfg):
        """structured-json sink has format=json."""
        s = sink_desc(cfg, "structured-json")
        assert s.as_str("format") == "json"

    def test_console_sink_has_no_path(self, cfg):
        """console sink has no 'path' key — navigate returns Ellipsis."""
        s = sink_desc(cfg, "console")
        assert s.navigate("path") is ...

    def test_console_sink_colorize_is_false(self, cfg):
        """console sink: colorize boolean False is read correctly."""
        s = sink_desc(cfg, "console")
        assert s.as_bool("colorize") is False

    def test_sink_path_verbatim_keeps_expression(self, cfg):
        """verbatim=True: the raw $(paths/logs) template is returned unexpanded."""
        s = sink_desc(cfg, "app-file")
        assert s.as_str("path", verbatim=True) == "$(paths/logs)/app.log"

    def test_app_file_keep_days(self, cfg):
        """app-file: keep integer returned correctly."""
        s = sink_desc(cfg, "app-file")
        assert s.as_int("keep") == 7

    def test_error_file_keep_days(self, cfg):
        """error-file: long retention period (30 days)."""
        s = sink_desc(cfg, "error-file")
        assert s.as_int("keep") == 30

    def test_audit_file_keep_days(self, cfg):
        """audit-file: yearly retention (365 days)."""
        s = sink_desc(cfg, "audit-file")
        assert s.as_int("keep") == 365

    def test_app_file_rotate_is_true(self, cfg):
        s = sink_desc(cfg, "app-file")
        assert s.as_bool("rotate") is True

    def test_app_file_min_level(self, cfg):
        s = sink_desc(cfg, "app-file")
        assert s.as_str("min-level") == "INFO"

    def test_error_file_min_level(self, cfg):
        s = sink_desc(cfg, "error-file")
        assert s.as_str("min-level") == "ERROR"


# ===========================================================================
# 5.  DB stores — per-store Descriptors scoped to root for $(uris/…) expansion
# ===========================================================================

class TestMongoPrimary:
    def test_connect_string_expands(self, cfg):
        """$(uris/mongo-primary) is substituted with the actual host:port pair."""
        s = store_desc(cfg, "mongo-primary")
        assert s.as_str("connect") == "mongodb://mongo1.corp:27017,mongo2.corp:27017/warehousedb?replicaSet=rs0"

    def test_connect_verbatim_keeps_expression(self, cfg):
        """verbatim=True: the raw $(uris/…) token is left untouched."""
        s = store_desc(cfg, "mongo-primary")
        assert s.as_str("connect", verbatim=True) == "mongodb://$(uris/mongo-primary)/warehousedb?replicaSet=rs0"

    def test_type(self, cfg):
        s = store_desc(cfg, "mongo-primary")
        assert s.as_str("type") == "mongodb"

    def test_fetch_by(self, cfg):
        s = store_desc(cfg, "mongo-primary")
        assert s.as_int("fetch-by") == 500

    def test_null_treatment(self, cfg):
        s = store_desc(cfg, "mongo-primary")
        assert s.as_str("null-treatment") == "omit"

    def test_tls_enabled(self, cfg):
        s = store_desc(cfg, "mongo-primary")
        assert s.as_bool("options/tls") is True

    def test_max_pool_size(self, cfg):
        s = store_desc(cfg, "mongo-primary")
        assert s.as_int("options/max-pool-size") == 50

    def test_auth_mechanism(self, cfg):
        s = store_desc(cfg, "mongo-primary")
        assert s.as_str("options/auth-mechanism") == "SCRAM-SHA-256"


class TestMongoArchive:
    def test_connect_string_expands(self, cfg):
        """$(uris/mongo-archive) resolves to the archive host:port."""
        s = store_desc(cfg, "mongo-archive")
        assert s.as_str("connect") == "mongodb://mongo-arc.corp:27017/archivedb"

    def test_connect_verbatim_keeps_expression(self, cfg):
        s = store_desc(cfg, "mongo-archive")
        assert s.as_str("connect", verbatim=True) == "mongodb://$(uris/mongo-archive)/archivedb"

    def test_fetch_by(self, cfg):
        s = store_desc(cfg, "mongo-archive")
        assert s.as_int("fetch-by") == 1000

    def test_null_treatment(self, cfg):
        s = store_desc(cfg, "mongo-archive")
        assert s.as_str("null-treatment") == "preserve"

    def test_tls_disabled(self, cfg):
        s = store_desc(cfg, "mongo-archive")
        assert s.as_bool("options/tls") is False

    def test_read_preference(self, cfg):
        s = store_desc(cfg, "mongo-archive")
        assert s.as_str("options/read-preference") == "secondaryPreferred"

    def test_max_staleness(self, cfg):
        s = store_desc(cfg, "mongo-archive")
        assert s.as_int("options/max-staleness-seconds") == 120


class TestMssqlCrm:
    def test_connect_string_expands(self, cfg):
        """$(uris/mssql-crm) resolves to the SQL Server host,port token."""
        s = store_desc(cfg, "mssql-crm")
        assert s.as_str("connect") == (
            "Server=sql-crm.corp,1433;Database=CRM;"
            "Encrypt=True;TrustServerCertificate=False;"
            "ApplicationName=warehouse-svc"
        )

    def test_connect_verbatim_keeps_expression(self, cfg):
        s = store_desc(cfg, "mssql-crm")
        assert s.as_str("connect", verbatim=True) == (
            "Server=$(uris/mssql-crm);Database=CRM;"
            "Encrypt=True;TrustServerCertificate=False;"
            "ApplicationName=warehouse-svc"
        )

    def test_schema(self, cfg):
        s = store_desc(cfg, "mssql-crm")
        assert s.as_str("schema") == "dbo"

    def test_fetch_by(self, cfg):
        s = store_desc(cfg, "mssql-crm")
        assert s.as_int("fetch-by") == 200

    def test_null_treatment(self, cfg):
        s = store_desc(cfg, "mssql-crm")
        assert s.as_str("null-treatment") == "dbnull"

    def test_multi_subnet_failover(self, cfg):
        s = store_desc(cfg, "mssql-crm")
        assert s.as_bool("options/multi-subnet-failover") is True

    def test_mars_disabled(self, cfg):
        s = store_desc(cfg, "mssql-crm")
        assert s.as_bool("options/mars") is False

    def test_command_timeout(self, cfg):
        s = store_desc(cfg, "mssql-crm")
        assert s.as_int("options/command-timeout-sec") == 120

    def test_max_pool_size(self, cfg):
        s = store_desc(cfg, "mssql-crm")
        assert s.as_int("options/max-pool-size") == 20


class TestOracleErp:
    def test_connect_string_expands(self, cfg):
        """Both $(uris/oracle-erp-host) and $(uris/oracle-erp-port) expand inside the TNS string."""
        s = store_desc(cfg, "oracle-erp")
        assert s.as_str("connect") == (
            "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)"
            "(HOST=ora-erp.corp)(PORT=1521))"
            "(CONNECT_DATA=(SERVICE_NAME=ERPPRD)))"
        )

    def test_connect_verbatim_keeps_expression(self, cfg):
        s = store_desc(cfg, "oracle-erp")
        assert s.as_str("connect", verbatim=True) == (
            "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)"
            "(HOST=$(uris/oracle-erp-host))(PORT=$(uris/oracle-erp-port)))"
            "(CONNECT_DATA=(SERVICE_NAME=ERPPRD)))"
        )

    def test_user(self, cfg):
        s = store_desc(cfg, "oracle-erp")
        assert s.as_str("user") == "erp_ro"

    def test_schema(self, cfg):
        s = store_desc(cfg, "oracle-erp")
        assert s.as_str("schema") == "ERP"

    def test_fetch_by(self, cfg):
        s = store_desc(cfg, "oracle-erp")
        assert s.as_int("fetch-by") == 100

    def test_null_treatment(self, cfg):
        s = store_desc(cfg, "oracle-erp")
        assert s.as_str("null-treatment") == "preserve"

    def test_ha_events(self, cfg):
        s = store_desc(cfg, "oracle-erp")
        assert s.as_bool("options/ha-events") is True

    def test_load_balancing(self, cfg):
        s = store_desc(cfg, "oracle-erp")
        assert s.as_bool("options/load-balancing") is True

    def test_statement_cache_size(self, cfg):
        s = store_desc(cfg, "oracle-erp")
        assert s.as_int("options/statement-cache-size") == 50

    def test_connection_timeout(self, cfg):
        s = store_desc(cfg, "oracle-erp")
        assert s.as_int("options/connection-timeout-sec") == 15

    def test_min_pool_size(self, cfg):
        s = store_desc(cfg, "oracle-erp")
        assert s.as_int("options/min-pool-size") == 1


# ===========================================================================
# 6.  Cross-section isolation — scoped descriptor cannot see sibling keys
#     without the root scope, but CAN see them when scope=root is provided
# ===========================================================================

class TestScopeIsolation:
    def test_store_without_scope_cannot_expand_uris(self, cfg):
        """A Descriptor without scope= raises ConfigError on unresolvable $(uris/…)."""
        ok, data = cfg.try_navigate("db-stores/stores/$name=mongo-primary")
        assert ok
        unscoped = Descriptor(data)           # no scope → self-scope only
        with pytest.raises(ConfigError):
            unscoped.as_str("connect")

    def test_store_with_scope_expands_uris(self, cfg):
        """The same data node resolves correctly when scope=root is supplied."""
        s = store_desc(cfg, "mongo-primary")  # scope=cfg (root)
        assert "$(uris/mongo-primary)" not in s.as_str("connect") # type: ignore

    def test_sink_without_scope_cannot_expand_paths(self, cfg):
        """Log sink Descriptor without scope= raises ConfigError on unresolvable $(paths/logs)."""
        ok, data = cfg.try_navigate("log/sinks/$name=app-file")
        assert ok
        unscoped = Descriptor(data)
        with pytest.raises(ConfigError):
            unscoped.as_str("path")

    def test_sink_with_scope_expands_paths(self, cfg):
        """Log sink Descriptor with scope=root correctly expands $(paths/logs)."""
        s = sink_desc(cfg, "app-file")
        assert "$(paths/logs)" not in s.as_str("path") # type: ignore
