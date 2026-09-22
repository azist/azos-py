-- -------------------------------------------------------------------------
-- Azos Sky SGA Creation script
--
-- Original design reference:
--   https://github.com/azist/azos/tree/master/src/Azos.Sky/Fabric
--   https://github.com/azist/azos/tree/master/src/Azos.Sky.Server/Locking
--
-- Copyright (C) 2020 - 2026 Azist, MIT License
-- -------------------------------------------------------------------------
-- call it like so:
--   psql -h localhost -U sysdba -v db_name=sga_memory -f src/azos/sky/memory.pg.sql
-- -------------------------------------------------------------------------

-- -------------------------------------------------------------------------
-- ATTENTION!!!
-- This script represents the carefully designed and well-balanced solution
-- for the specific purpose, such as SGA Distributed Memory which is NEVER accessed directly.
-- The database here acts like a system memory storage engine, not a business application.
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
    LC_COLLATE = 'C.UTF-8'    -- case sensitive binary collation
    LC_CTYPE = 'C.UTF-8'      -- case sensitive binary collation
    LOCALE_PROVIDER = 'libc'  -- standard str comparison
    TEMPLATE = template0;     -- must be used for no collations

-- WARNING: DO NOT use `timestamptz` type, it converts dates silently and leads to hard-to find bugs
-- In THIS system design we treat all system dates as UTC timestamps only.
-- Do not convert anything automatically
ALTER DATABASE :"db_name" SET "TimeZone" TO 'UTC';

-- Connect to the new database before creating tables (psql syntax)
\c :"db_name"

-- create table
create table tbl_mutex
(
    "gdid"        bigint         not null,
    "name"        varchar(128)   not null,
    "owner"       varchar(128)   not null,
    "timeout"     double precision not null,
    "acquire_utc" timestamp      not null,

    -- System columns for versioning
    "ver_state"   char(1)        not null,
    "ver_utc"     timestamp      not null,
    "ver_actor"   varchar(128)   not null,
    "ver_origin"  bigint         not null,

    primary key ("name")
)


create table tbl_ram_slot
(
    "table"       varchar(128)   not null,
    "key"         varchar(128)   not null,
    "value"       jsonb          not null,
    "timeout"     double precision not null,
    "component"   varchar(128)   not null,
    "description" varchar(256)   not null,

    -- System columns for versioning
    "ver_state"   char(1)        not null,
    "ver_utc"     timestamp      not null,
    "ver_actor"   varchar(128)   not null,
    "ver_origin"  bigint         not null,

    primary key ("table", "key")
)


create table tbl_task
(
    "gdid"        bigint         not null,
    "name"        varchar(128)   not null,
    "owner"       varchar(128)   not null,
    "timeout"     double precision not null,
    "schedule_utc" timestamp      not null,

    -- System columns for versioning
    "ver_state"   char(1)        not null,
    "ver_utc"     timestamp      not null,
    "ver_actor"   varchar(128)   not null,
    "ver_origin"  bigint         not null,

    primary key ("name")
)


create table tbl_taskslice
(

)
