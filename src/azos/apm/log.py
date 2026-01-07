"""Provides structured logging support
Copyright (C) 2025-2026 Azist, MIT License

"""
import sys
import logging
import json
import uuid
import datetime
import contextvars

from typing import Callable
from azos.application import Application
from azos.conio import ANSIColors


LOG_SCHEMA_VERSION = 0
"""Current log schema implementation version"""

CFG_LOG_SECTION = "log"
"""Configuration log section name: [log]"""

CFG_LOG_LEVEL_ATTR_PFX = "log-"
"""Log level attribute prefix, e.g. `log-db=ERROR` - sets error level logging for `db` logger """

LOG_CHANNEL_APP = "app"
"""Default application log channel"""

LOG_CHANNEL_DEFAULT = LOG_CHANNEL_APP
"""Default log channel (app)"""

LOG_CHANNEL_OTEL = "otel"
"""Open telemetry data"""

LOG_CHANNEL_OPLOG = "oplog"
"""Oplog channel is used to trace business operations, such as requests/response bodies"""

LOG_CHANNEL_SEC = "sec"
"""Security events"""

LOG_CHANNEL_ANL = "anl"
"""Analytics, such as dashboard feeds"""

# supports threading and async such as FastApi etc.
_ts_log_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("log_id", default=None)


def new_log_id() -> str:
  """
  Generates new LOG id which you may want to track for correlation of log messages using `rel` parameter
  of strands or manually adding it to extra collection as `sys_rel`
  """
  result = uuid.uuid4().hex
  _ts_log_id.set(result)
  return result


class AzLogRecord(logging.LogRecord):
    """
    A derivative of LogRecord that adheres to uniform Azos/Sky schema
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
          nid = _ts_log_id.get()
          self.sys_id = nid if nid else new_log_id()
        finally:
          _ts_log_id.set(None)

        chassis = Application.get_current_instance()
        self.sys_app = chassis.app
        self.sys_app_inst = chassis.instance_tag
        self.sys_host = chassis.host


# Custom log factory function
def _az_log_record_factory(*args, **kwargs):
    """
    Factory function that returns an instance of our our AzLogRecord.
    Forwarding all arguments to the constructor.
    """
    return AzLogRecord(*args, **kwargs)


class AzLogRecordFormatter(logging.Formatter):
    """
    Provides base implementation for Azos log formatters
    """
    EXCLUDED_DATA_FIELDS = (set(
        dir(logging.LogRecord(name="", level=0, pathname="", lineno=0, msg='', args=(), exc_info=None))
    ))


    _hook_enrichment_func: Callable[[logging.Formatter, logging.LogRecord, dict], None] | None = None
    """
    Internal hook used to set up logging enrichment with attributes such as OpenTelemetry traces
    the function takes: (AzLogRecordFormatter, LogRecord, dict) params
    Business developers: DO NOT use this hook, it is for internal use and should be avoided in business code
    """

    def enrich(self, record: AzLogRecord, log_record: dict) -> None:
        """
        Override to enrich log with extra values like OTP tracing.
        Default implementation calls the hook
        """
        if callable(AzLogRecordFormatter._hook_enrichment_func):
            AzLogRecordFormatter._hook_enrichment_func(self, record, log_record)


    def format(self, record: logging.LogRecord):
        """
        Prepares structured logging structure:
        This is ideal for structured logging in containerized environments.
        """

        if not isinstance(record, AzLogRecord):
            return super().format(record)

        # Start with the basic log record attributes
        log_record = {
            "id": record.sys_id,
            "rel": None,
            "chn": LOG_CHANNEL_DEFAULT,
            "lvl": record.levelname,
            "utc": int(record.created * 1000),
            "lts": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "hst": record.sys_host,
            "app": record.sys_app,
            "ain": record.sys_app_inst,
            "nm": "/" if record.name=="root" else record.name,
            "frm": f"{"@" if record.funcName == "<module>" else record.funcName}@{record.filename}:{record.lineno}",
            "msg": record.getMessage(),
        }

        # Add conditionals
        if hasattr(record, 'sys_rel'):
            log_record['rel'] = record.sys_rel # pyright: ignore[reportAttributeAccessIssue]

        if hasattr(record, 'sys_channel'):
            log_record['chn'] = record.sys_channel # pyright: ignore[reportAttributeAccessIssue]

        if record.exc_info:
           log_record['error'] = self.formatException(record.exc_info)

        ## Data
        data = { }
        for attr in dir(record):
            if (not attr.startswith('_') and
                not attr.startswith("sys_") and
                not attr in AzLogRecordFormatter.EXCLUDED_DATA_FIELDS):
                val = getattr(record, attr)
                # Skip methods and callable attributes
                if not callable(val):
                    data[attr] = val

        if len(data) > 0:
            log_record["d"] = data

        log_record["v"] = LOG_SCHEMA_VERSION

        self.enrich(record, log_record)

        return self.do_format(record, log_record)

    def do_format(self, record, log_record):
        """
        Override to do the actual formatting like DEV console or k8s JSON
        """
        return f"UNIMPLEMENTED FORMATTER: {record.msg}"


class AzLogRecordJsonFormatter(AzLogRecordFormatter):
    """
    Implements formatter for K8s structured log streaming
    """
    def do_format(self, record, log_record):
        """
        Formats as terse json for K8s streaming
        """
        return json.dumps(log_record, separators=(',', ':'))


class AzLogRecordVisualFormatter(AzLogRecordFormatter):
    # Map logging level constants to literal color names
    COLOR_MAP = {
        logging.DEBUG: "BLUE",
        logging.INFO: "GREEN",
        logging.WARNING: "YELLOW",
        logging.ERROR: "RED",
        logging.CRITICAL: "PURPLE",
    }

    def do_format(self, record: logging.LogRecord, log_record: dict):
        """Formats for a rich visual presentation in dev console"""
        segs = []
        fg1 = ANSIColors.color(self.COLOR_MAP.get(record.levelno, 'WHITE'), bright=True, fg=True)
        fg2 = ANSIColors.color(self.COLOR_MAP.get(record.levelno, 'WHITE'), bright=False, fg=True)

        lvl = f"{fg1}╔═╣{log_record['lvl']}╠══╣{log_record['id'][:8]}║{ANSIColors.RESET}"
        msg = f"{fg1}╚═>{fg2}{log_record['msg']}{ANSIColors.RESET}"
        otl = log_record.get("oti")
        if otl:
            otl = (
                f"{ANSIColors.FG_YELLOW}■ {ANSIColors.FG_BRIGHT_MAGENTA}{otl}{ANSIColors.FG_GRAY}-"
                f"{ANSIColors.FG_CYAN}{log_record.get('ots','none')}{ANSIColors.RESET}"
            )
        else:
            otl = ""

        segs.append(f"{lvl} {ANSIColors.FG_GRAY} {log_record['lts']} ■ {ANSIColors.FG_BRIGHT_WHITE}{log_record['chn']}{ANSIColors.RESET}")
        segs.append(f"«{log_record['nm']}» {ANSIColors.FG_GRAY}{log_record['frm']}{ANSIColors.RESET}")
        segs.append(f"{ANSIColors.FG_CYAN}{log_record['rel'][:8] if log_record.get('rel') else ''}{ANSIColors.RESET}")
        segs.append(f"{otl}")
        segs.append(f"{msg}")

        if "d" in log_record:
            js = json.dumps(log_record["d"])
            segs.append(f" \n {ANSIColors.FG_GRAY}   └─► {js}{ANSIColors.RESET}")

        err = log_record.get("error", None)
        if err:
            err = err.replace("\n", f"\n {ANSIColors.FG_BRIGHT_RED}░{ANSIColors.FG_RED}       ")
            segs.append(f" \n     └─► {err}{ANSIColors.RESET}")

        return "".join(segs)


class AzLogRecordTerseFormatter(AzLogRecordVisualFormatter):
    #todo: implement terse formatter
    pass

class AzLogStrand(logging.LoggerAdapter):
    """
    Creates a named log conversation topic optionally grouping all log  messages with REL tag and
    putting them on specified channel
    """
    def __init__(self, logger_name: str | None, rel: str | None = None, channel: str | None = None):
        """
        Initializes a named logger with optional REL correllation and channel assignment

        :param self: self ref
        :param logger_name (str | None): case-insensitive logger name (converted to lower case)
        :param rel (str | None) Optional corrwlation id to be applied to all log messages emittrd by this strand
        :param channel (str | None): Optional channel name to categorize log messages
        """
        logger = logging.getLogger(logger_name.lower()) # case-insensitive
        super().__init__(logger, {})

        #pre-generate ID to be used in correlation
        self.strand_id = new_log_id()
        self.rel = self.strand_id if rel == "self" else rel
        self.channel = channel


    def process(self, msg, kwargs):
        """
        Merges the adapter's 'extra' context with any 'extra' context
        passed explicitly in the log call.
        """
        # 1. Start with the ambient context (self.extra)
        context = self.extra.copy()  if self.extra  else { } # pyright: ignore[reportAttributeAccessIssue]

        # 2. Set log thread context
        if self.rel:
            context["sys_rel"] = self.rel
        if self.channel:
            context["sys_channel"] = self.channel

        # 3. Update with any specific context passed in this log call
        if 'extra' in kwargs:
            context.update(kwargs['extra'])

        # 4. Place back into kwargs
        kwargs['extra'] = context
        return msg, kwargs



###################################
##### BUILD LOGGING PIPELINE ######
###################################
# The code below is a bit strange because
# it is built to work in both regular Python applications where
# a module inclusion is sufficient
# AND
# PySpark UDF. The PySpark "teleports"/serializes/pickles the user lambdas
# hence they lose the context, therefore you need to get your pyspark logger
# via a call to `get_pyspark_logger(name) -> Logger` from withing your UDF func body
#warning: do not use __ mangling for Spark UDF teleportation
def _activate_az_logging() -> None:

  # one time use Latch
  if logging.getLogRecordFactory() is az_log_record_factory: return

  # 1. Set the Factory (Global Change) ---
  # This is a one-time setup that affects ALL loggers in the process.
  logging.setLogRecordFactory(az_log_record_factory)

  # 2. Get root logger
  root = logging.getLogger()
  root.setLevel(logging.DEBUG)

  # 3. Create the Handler (StreamHandler directs output to sys.stdout/stderr)
  # We explicitly target sys.stdout for all general logs
  handler = logging.StreamHandler(sys.stdout)

  # 4. Formatter and set to handler
  # todo: Here access config to set DEV formatter for local workstation use
  formatter = AzLogRecordJsonFormatter()
  handler.setFormatter(formatter)

  # 5. Clear any existing handlers and add the new one
  if root.hasHandlers():
      root.handlers.clear()

  # 6. Activate handler at root
  root.addHandler(handler)


#to be used in PySpark jobs
def get_pyspark_logger(name: str | None) -> logging.Logger:
    """Useful in PySpark teleported code aka UDFs. Call this method to get proper logger"""
    _activate_az_logging();
    logger = logging.getLogger(f"PySpark::{name}" if name else "PySpark")
    return logger

# Activate globally
_activate_az_logging()
#end.
