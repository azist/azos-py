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
    "value"       varchar(8192)  not null, -- Value for the key in the namespace


    constraint "pk_mutex" primary key ("gdid"),
    constraint "uk_mutex" unique ("ns", "key")
);

-- NO Additional indexes ON PURPOSE!!!
comment on table tbl_mutex is 'Mutex table holds ephemeral [NS:KEY -> Value] tuples used for process coordination via mutual exclusion';
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




-- Slot table holds a limited set of rows (< 10k) each representing a [NS:KEY -> Value] tuple.
-- If the [NS:KEY] already exists the system replaces the value (unlike the mutex which throws).
-- You can set optional `end_utc` to auto-expire the slot.
-- Slots are used as cluster-global memory addressable by [NS:KEY]. It is a regular LOGGED table (unlike mutex).
-- Slots do NOT provide any synchronization, so your process needs to use global memory under a MUTEX
-- critical section block, otherwise other process may mutate the same slot which may be a desired
-- behavior for some speculative algorithms built for performance, such as "the last wins".
create table tbl_slot
(
    "gdid"        bigint         not null, -- Unique GDID - PK
    "set_app"     varchar(32)    not null, -- Process app id that set the slot
    "set_cmp"     varchar(128)   not null, -- Component id that set the slot
    "set_host"    varchar(128)   not null, -- Host name that set the slot
    "set_utc"     timestamp      not null, -- When slot was set
    "set_actor"   varchar(128)   not null, -- Entity id - who set the slot (user id etc..)
    "set_origin"  bigint         not null, -- Cloud origin where slot was set (datacenter id)
    "end_utc"     timestamp,               -- Absolute point in time after which slot gets deleted (this-set_utc) = timeout
    "description" varchar(256)   not null, -- Display description line for debugging

    "ns"          varchar(128)   not null, -- Slot namespace
    "key"         varchar(256)   not null, -- Unique Key in the namespace
    "value"       jsonb          not null, -- Value for the key in the namespace


    constraint "pk_slot" primary key ("gdid"),
    constraint "uk_slot" unique ("ns", "key"),
    -- Enforce a 1 MB ceiling on the serialized JSON payload size.
    -- jsonb is a varlena type capped at ~1 GB; this constraint bounds it
    -- to 1 MB (1048576 bytes) to protect the SGA memory engine.
    constraint chk_slot_value_max_1mb check (octet_length("value"::text) <= 1048576)
);

-- NO Additional indexes ON PURPOSE!!!
comment on table tbl_slot is 'Slot table holds cluster global [NS:KEY -> Value] tuples';
comment on column tbl_slot."gdid"        is 'Unique GDID - PK';
comment on column tbl_slot."set_app"     is 'Process app id that set the slot';
comment on column tbl_slot."set_cmp"     is 'Component id that set the slot';
comment on column tbl_slot."set_host"    is 'Host name that set the slot';
comment on column tbl_slot."set_utc"     is 'When slot was set';
comment on column tbl_slot."set_actor"   is 'Entity id - who set the slot (user id etc..)';
comment on column tbl_slot."set_origin"  is 'Cloud origin where slot was set (datacenter id)';
comment on column tbl_slot."end_utc"     is 'Absolute point in time after which slot gets deleted (this-set_utc) = timeout';
comment on column tbl_slot."description" is 'Display description line for debugging';
comment on column tbl_slot."ns"          is 'Slot namespace';
comment on column tbl_slot."key"         is 'Unique Key in the namespace';
comment on column tbl_slot."value"       is 'Value for the key in the namespace';



-- Task
create table tbl_task
(
    "gdid"        bigint         not null, -- Task unique ID
    "ctag"        uuid           not null, -- Task correlation tag
    "title"       varchar(64)    not null, -- Task title used for admin purposes
    "app"         varchar(32)    not null, -- Application to execute
    "cmp"         varchar(128)   not null, -- Application component within application to execute
    "nice"        int            not null, -- Task niceness similar to .NIX
    "sd_utc"      timestamp      not null, -- Start date: task can not start before this date
    "ed_utc"      timestamp      not null, -- After this date task would not run. If it has not started it will become stale

    "g_antecedent"   bigint,               -- Optional task which acts as a guard that prevents execution of this one until it is completed (200 or 500).
                                           -- This task will start execution when SD/ED allows AND the antecedent task is completed with 200 or 500 status code.
                                           -- If antecedent task is deleted that this task will not execute and become stale

    "exec_actor"  varchar(128)   not null, -- Security principal on behalf of which the task executes

    "status"      smallint       not null, -- 0=created, 100=running, 200=succeeded, 500=failed
    "status_msg"  varchar(64),             -- Optional status message for admin/debug purposes
    "status_utc"  timestamp      not null, -- the UTc stamp as of which the status is set

-- Need to track status host, app inst, (app/cmp) already in task


    "target_id"   varchar(128)   not null, -- target context ID, such as a FILE to process
    "args"        jsonb          not null, -- Task Arguments
    "result"      jsonb,                   -- Task execution result, error if [Failed] or non error is [Succeeded]

    "crt_app"     varchar(32)    not null, -- Process app id that created the task
    "crt_cmp"     varchar(128)   not null, -- Component id that created the task
    "crt_host"    varchar(128)   not null, -- Host name that created the task
    "crt_utc"     timestamp      not null, -- When task was created
    "crt_actor"   varchar(128)   not null, -- Entity id - who created the task (user id etc..)
    "crt_origin"  bigint         not null, -- Cloud origin where task was created (datacenter id)

    constraint "pk_task" primary key ("gdid"),
    constraint "fk_task_antecedent" foreign key ("g_antecedent") references "tbl_task"("gdid")
);

-- Index on date for point in time queries: find all tasks that are active at a given point in time for app/cmp
create index "idx_task_dtappcmp_utc" on "tbl_task" ("ed_utc", "sd_utc", "app", "cmp");

-- Find by correlation tag/logging
create index "idx_task_ctag" on "tbl_task" ("ctag");

-- Index on Target_id
create index "idx_task_target_id" on "tbl_task" ("target_id");


-- UNDER construction
create table tbl_taskslice
(
    "gdid"        bigint         not null, -- Task Slice unique ID
    "g_task"      bigint         not null, -- FK Task
    "seq"         int            not null, -- Slice sequence number within task
    "status"      smallint       not null, -- 0=created, 100=running, 200=succeeded, 500=failed
    "status_msg"  varchar(64),             -- Optional status message for admin/debug purposes
    "args"        jsonb          not null,
    "result"      jsonb,                   -- Task execution result, error if [Failed] or non error is [Succeeded]

    "start_host"  varchar(128)   not null, -- Host name that started execution
    "start_utc"   timestamp,               -- When slice was started
    "end_utc"     timestamp,               -- When slice was completed (succeeded or failed)

-- max-retries? backoff settings?/policies

-- need to track who started: host, app instance (app/component already in task table)


    constraint "pk_taskslice" primary key ("gdid"),
    constraint "uk_taskslice" unique ("g_task", "seq"),
    constraint "fk_taskslice_task" foreign key ("g_task") references "tbl_task"("gdid")
);
