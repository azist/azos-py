-- -------------------------------------------------------------------------
-- Azos Sky CTREE Creation script
--
-- Original design reference:
--   https://github.com/azist/azos/tree/master/src/Azos/Conf/Forest
--
-- Copyright (C) 2020 - 2026 Azist, MIT License
-- -------------------------------------------------------------------------
-- call it like so:
--     psql -v db_name=my_configured_db -f src/azos/sky/ctree.pg.sql
-- -------------------------------------------------------------------------

-- -------------------------------------------------------------------------
-- ATTENTION!!!
-- This script represents the carefully designed and well-balanced solution
-- for the specific purpose, such as SGA Sysdat catalog which is NEVER accessed directly.
-- The database here acts like a system config storage engine, not a business application.
-- No one will ever consume this data directly by bypassing special system API methods.
-- Database administrators should not alter this script "to improve it"
-- Do not create or modify any database objects manually; do not create indexes;
-- do not change object casing or alter column sizes manually use the provided
-- script as is otherwise you may easily break the system integrity.
-- -------------------------------------------------------------------------


-- Assuming db_name is passed externally via psql -v db_name=my_db_name
-- If you are using a scripting tool instead, use its specific variable syntax (e.g. $db_name)
CREATE DATABASE :"db_name"
    WITH
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    LOCALE_PROVIDER = 'libc'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1
    IS_TEMPLATE = False;


-- WARNING: DO NOT use `timestamptz` type, it converts dates silently and leads to hard-to find bugs
-- In THIS system design we treat all system dates as UTC timestamps only.
-- Do not convert anything automatically
ALTER DATABASE :"db_name" SET "TimeZone" TO 'UTC';

-- Connect to the new database before creating tables (psql syntax)
\c :"db_name"

-- Configuration tree table, simplified design keeping parent/child path relationships pre-rendered
-- in "path"
create table "tbl_ctree"
(
    "gdid"        bigint         not null,
    "path"        varchar(650)   not null, -- 2712 bytes pg SQL limit for indexable varchar (650 * 4 + overhead)
    "asof_utc"    timestamp      not null,
    "props"       jsonb          not null,
    "config"      jsonb          not null,

    -- System columns for versioning
    "ver_state"   char(1)        not null,
    "ver_utc"     timestamp      not null,
    "ver_actor"   varchar(128)   not null,
    "ver_origin"  bigint         not null,

    constraint "pk_ctree" primary key ("gdid"),
    constraint "uk_ctree" unique ("path", "asof_utc"), -- must fit in 2712 bytes (max indexable varchar length)
    constraint "chk_ctree_ver_state" check ("ver_state" in ('c', 'u', 'd'))
);


create index "idx_ctree_ver" on "tbl_ctree" ("ver_utc");
create index "idx_ctree_props" on "tbl_ctree" using GIN ("props" jsonb_path_ops);

-- -------------------------------------------------------------------------
-- Comments for documentation & tooling
-- -------------------------------------------------------------------------
COMMENT ON TABLE "tbl_ctree" IS 'Configuration tree node properties and settings';

COMMENT ON COLUMN "tbl_ctree"."gdid" IS 'Global Distributed ID/GDID8; Snowflake-style unique identifier for the node';
COMMENT ON COLUMN "tbl_ctree"."path" IS 'Absolute node path in the config tree';
COMMENT ON COLUMN "tbl_ctree"."asof_utc" IS 'Timestamp indicating the effective time of this configuration';
COMMENT ON COLUMN "tbl_ctree"."props" IS 'Node properties in JSON format. Props are not computed from parent level';
COMMENT ON COLUMN "tbl_ctree"."config" IS 'Node configuration in JSON format. Configuration gets computed from the root';
COMMENT ON COLUMN "tbl_ctree"."ver_state" IS 'Version state (e.g., [c]reated, [u]pdated, [d]eleted)';
COMMENT ON COLUMN "tbl_ctree"."ver_utc" IS 'Timestamp indicating when this version was created';
COMMENT ON COLUMN "tbl_ctree"."ver_actor" IS 'Actor who made this version change';
COMMENT ON COLUMN "tbl_ctree"."ver_origin" IS 'Origin/Datacenter atom of the version change (e.g., "east1")';


COMMENT ON CONSTRAINT "pk_ctree" ON "tbl_ctree" IS 'Primary lookup constraint/index by GDID';
COMMENT ON CONSTRAINT "uk_ctree" ON "tbl_ctree" IS 'Guarantees that a path can only have one configuration at a given point in time';
COMMENT ON INDEX "idx_ctree_ver" IS 'Facilitates getting change logs';
COMMENT ON INDEX "idx_ctree_props" IS 'Facilitates node props scanning';

---- Example tree node retrieval by path as of date: (a 99+% use case)
-- SELECT
--     "gdid",
--     "asof_utc",
--     "props",
--     "config",
--     "ver_state",
--     "ver_utc",
--     "ver_actor",
--     "ver_origin"
-- FROM
--     "tbl_ctree"
-- WHERE
--     "path" = '/rule/ch/ingress/contoso/patients'
--     AND "asof_utc" <= '2026-04-12 00:00:00'
-- ORDER BY
--     "asof_utc" DESC
-- LIMIT 1;
