"""Provides structured logging support
Copyright (C) 20025 Azist, MIT License

"""
import logging
import json
import uuid
import sys
from  typing import Callable
import datetime
import threading
import platform

LOG_SCHEMA_VERSION = 0
INSTANCE_ID = str(uuid.uuid4())[:8] # Shortened UUID for brevity

LOG_HOST = platform.node()

__ts_log_id = threading.local()
__ts_log_id.val = None

def newLogRecordId():
  """
  Generates new LOG id which you may want to track for correlation of log messages using `rel` parameter
  of strands or manually adding it to extra collection as `sys_rel`
  """
  result = uuid.uuid4().hex
  __ts_log_id.val = result
  return result

# Sets our schema
class AzLogRecord(logging.LogRecord):
    """
    A derivative of LogRecord that adheres to our uniform schema
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
          id = __ts_log_id.val
          self.sys_id = id if id else newLogRecordId()
        finally:
          __ts_log_id.val = None

        self.sys_app = "demo" #todo: map!!!!
        self.sys_app_inst = INSTANCE_ID


# Custom log factory function
def az_log_record_factory(*args, **kwargs):
    """
    Factory function that returns an instance of our our AzLogRecord.
    Forwarding all arguments to the constructor.
    """
    return AzLogRecord(*args, **kwargs)


class AzLogRecordFormatter(logging.Formatter):
    """
    Provides base implementation for Azos log formatters
    """
    EXCLUDED_DATA_FIELDS = ( set(dir(logging.LogRecord(name="", level=0, pathname="",
                                 lineno=0, msg='', args=(), exc_info=None))))

    """
    Internal hook used to set up logging enrichment with attributes such as OpenTelemetry traces
    the function takes: (AzLogRecordFormatter, LogRecord, dict) params
    Business developers: DO NOT use this hook, it is for internal use and should be avoided in business code
    """
    _hook_enrichment_func: Callable[[logging.Formatter, logging.LogRecord, dict], None] | None = None

    def enrich(self, record: AzLogRecord, log_record: dict) -> None:
        """
        Override to enrich log with extra values like OTP tracing.
        Default implementation calls the hook
        """
        if callable(AzLogRecordFormatter._hook_enrichment_func):
            AzLogRecordFormatter._hook_enrichment_func(self, record, log_record)


# Custom JSON formatter
    """
    Prepares structured logging structure:
    This is ideal for structured logging in containerized environments.
    """
    def format(self, record: logging.LogRecord):

        if not isinstance(record, AzLogRecord):
             return super().format(record)

        # Start with the basic log record attributes
        log_record = {
            "id": record.sys_id,
            "rel": None,
            "chn": "app",
            "lvl": record.levelname,
            "utc": int(record.created * 1000),
            "lts": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "hst": LOG_HOST,
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

        if len(data) > 0:  log_record["d"] = data

        log_record["v"] = LOG_SCHEMA_VERSION

        self.enrich(record, log_record)

        # Output the data
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


class AzLogStrand(logging.LoggerAdapter):
    """
    Creates a named log conversation topic optionally grouping all log
    messages with REL tag and putting them on specified channel
    """
    def __init__(self, loggerName, rel = None, channel = None):
        logger = logging.getLogger(loggerName)
        super().__init__(logger, { })

        #pre-generate ID to be used in correlation
        self.id = newLogRecordId()
        self.rel = rel
        self.channel = channel


    def process(self, msg, kwargs):
        """
        Merges the adapter's 'extra' context with any 'extra' context
        passed explicitly in the log call.
        """
        # 1. Start with the ambient context (self.extra)
        context = self.extra.copy()  if self.extra  else { } # pyright: ignore[reportAttributeAccessIssue]

        # 2. Set log thread context
        if self.rel: context["sys_rel"] = self.rel
        if self.channel: context["sys_channel"] = self.channel

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
def _activate_az_logging():

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
