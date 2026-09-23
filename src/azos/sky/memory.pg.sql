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

-- Mutex table holds a limited set of rows (< 1k) each representing a mutually-exclusive value
-- set in [NS:KEY -> Value] tuple. If the [NS:KEY] already exists the system fails the unique constraint
-- and does not allow to set duplicate key in the same namespace, effectively a namespace is a SET which
-- allows either absence or singular presence of a KEY at a time.
-- ATTENTION: This table does not have indexes as it is cheaper to execute certain operations (e.g. purge dead records)
-- using sequential search than maintain index on every insert/delete
-- ATTENTION: The table is UNLOGGED - it does not write to WAL and does not replicate to standby servers
-- this is by design as MUTEXES are ephemeral (unlike memory slots). UNLOGGED still saves data on clean shutdown, it only
-- loses data on unexpected Pg server crash which is ok
create unlogged table tbl_mutex
(
    "gdid"        bigint         not null, -- Unique GDID - PK
    "owner_app"   varchar(32)    not null, -- Process app id that owns the mutex
    "owner_cmp"   varchar(128)   not null, -- Component id that owns the mutex
    "set_host"    varchar(128)   not null, -- Host name that set the mutex
    "set_utc"     timestamp      not null, -- When mutex was set
    "set_actor"   varchar(128)   not null, -- Entity id - who set the mutex (user id etc..)
    "set_origin"  bigint         not null, -- Cloud origin where mutex was set (datacenter id)
    "end_utc"     timestamp      not null, -- Absolute point in time after which mutex gets deleted (this-set_utc) = timeout
    "description" varchar(256)   not null, -- Display description line for debugging

    "ns"          varchar(128)   not null, -- Mutex namespace
    "key"         varchar(256)   not null, -- Unique Key in the namespace
    "value"       jsonb          not null, -- Value for the key in the namespace


    constraint "pk_mutex" primary key ("gdid"),
    constraint "uk_mutex" unique ("ns", "key"),
    -- Enforce a 1 MB ceiling on the serialized JSON payload size.
    -- jsonb is a varlena type capped at ~1 GB; this constraint bounds it
    -- to 1 MB (1048576 bytes) to protect the SGA memory engine.
    constraint chk_mutex_value_max_1mb check (octet_length("value") <= 1048576)
);

comment on column tbl_mutex."gdid"        is 'Unique GDID - PK';
comment on column tbl_mutex."owner_app"   is 'Process app id that owns the mutex';
comment on column tbl_mutex."owner_cmp"   is 'Component id that owns the mutex';
comment on column tbl_mutex."set_host"    is 'Host name that set the mutex';
comment on column tbl_mutex."set_utc"     is 'When mutex was set';
comment on column tbl_mutex."set_actor"   is 'Entity id - who set the mutex (user id etc..)';
comment on column tbl_mutex."set_origin"  is 'Cloud origin where mutex was set (datacenter id)';
comment on column tbl_mutex."end_utc"     is 'Absolute point in time after which mutex gets deleted (this-set_utc) = timeout';
comment on column tbl_mutex."description" is 'Display description line for debugging';
comment on column tbl_mutex."ns"          is 'Mutex namespace';
comment on column tbl_mutex."key"         is 'Unique Key in the namespace';
comment on column tbl_mutex."value"       is 'Value for the key in the namespace';



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

    primary key ("table", "key"),

    -- Enforce a 1 MB ceiling on the serialized JSON payload size.
    constraint chk_ram_slot_value_max_1mb check (octet_length("value") <= 1048576)
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
