"""
Azos Open Telemetry Module
Copyright (C) 2026 Azist, MIT License
"""
from . import log
from azos.chassis import AppChassis

# Import OTEL SDK components via feature detection
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider, Tracer, StatusCode
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.trace.export import (BatchSpanProcessor,
                                                SpanExporter,
                                                ConsoleSpanExporter,
                                                SimpleSpanProcessor,
                                                SpanExportResult)
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
except ImportError as cause:
    raise ImportError(
        "Azos APM Open Telemetry module requires opentelemetry-sdk and related packages. "
        "Please install them via pip: "
        " pip install opentelemetry-api \\ "
        "             opentelemetry-sdk \\ "
        "             opentelemetry-exporter-otlp \ "
        "             opentelemetry-instrumentation-requests") from cause


CFG_OTEL_SECTION = "otel"
"""
Open Telemetry configuration section name, e.g. ini`[otel]` or laconic`otel{}`
"""

def get_tracer(name: str) -> Tracer:
    """
    Gets an OTEL tracer for the given name
    :param name: Tracer name, usually __name__
    :return: Tracer instance
    """
    return trace.get_tracer(name if name else __name__)

# Enriches our logs with OTEL cross correlation tokens
# this gets wired up into logging so you don't need to call this ever
def _log_otel_enricher(fmt: log.AzLogRecordFormatter, record: log.AzLogRecord, log_data) -> None:
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()
    trace_id = span_context.trace_id  # Integer
    span_id = span_context.span_id    # Integer
    if trace_id != 0:
        log_data["oti"] = trace.format_trace_id(trace_id)
    if span_id != 0:
        log_data["ots"] = trace.format_span_id(span_id)


class LogSpanExporter(SpanExporter):
    """
    An OTEL Span Exporter that writes spans to Azos LogStrand
    """

    def __init__(self, log_strand: log.LogStrand):
        self._log = log.LogStrand("otel.log", channel = log.LOG_CHANNEL_OTEL)

    def export(self, spans) -> SpanExportResult:
        for span in spans:
            self._log.info(f"OTEL Span Exported: {span.name}",
                extra= self.to_data(span))
        return SpanExportResult.SUCCESS

    def to_data(self, span) -> dict:
        ctx = span.get_span_context()
        data = {
            "treace_id": trace.format_trace_id(ctx.trace_id),
            "span_id": trace.format_span_id(ctx.span_id),
            "traceState": str(ctx.trace_state),
            "parent_span_id": trace.format_span_id(span.parent.span_id) if span.parent else None,
            "name": span.name,
            "kind": span.kind.name,
            "startTimeUnixNano": span.start_time,
            "endTimeUnixNano": span.end_time,

            "attributes": dict(span.attributes) if span.attributes else {},

            "events": [{"name": ev.name,
                        "timeUnixNano": ev.time_unix_nano,
                        "attributes": dict(ev.attributes)} for ev in span.events],

            "links": [{"trace_id": trace.format_trace_id(lnk.context.trace_id),
                       "span_id": trace.format_span_id(lnk.context.span_id),
                       "traceState": str(lnk.context.trace_state),
                       "attributes": dict(lnk.attributes)} for lnk in span.links],

            "status": {"code": span.status.status_code.value,
                       "message": span.status.description} if span.status.status_code != StatusCode.UNSET  else None
        }
        return {"otel": data}


__otel_configured = False

# Activates Open Telemetry based on the current AppChassis configuration
def __activate_otel() -> None:
    chassis = AppChassis.get_current_instance()
    conf = chassis.config

    if chassis.isdefault:
        return # must use real non-default instance to be able to bootstrap OTEL

    global __otel_configured
    if __otel_configured:
        return # May configure only once

    __otel_configured = True

    # Patch-in the hook to enrich our logs with OTEL info
    log.AzLogRecordFormatter._hook_enrichment_func = _log_otel_enricher

    srv_uri = None
    srv_insecure = True
    srv_timeout_sec = 20.0
    if conf.has_section(CFG_OTEL_SECTION):
        srv_uri = conf.get(CFG_OTEL_SECTION, "uri", fallback =  None)
        srv_insecure = conf.getbooean(CFG_OTEL_SECTION, "insecure", fallback = True)
        srv_timeout_sec = conf.getfloat(CFG_OTEL_SECTION, "timeout-sec", fallback = 20.0)


    resource = Resource.create({"service.name": chassis.app, "service.instance.id": chassis.instance_tag})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    if srv_uri and srv_uri != "":
        if srv_uri == "stdio" or srv_uri == "console":
            exporter = ConsoleSpanExporter()
            processor = SimpleSpanProcessor(exporter)
            provider.add_span_processor(processor)
        elif srv_uri == "log":
            exporter = LogSpanExporter()
            processor = SimpleSpanProcessor(exporter)
            provider.add_span_processor(processor)
        else:
            exporter = OTLPSpanExporter(endpoint=srv_uri, insecure=srv_insecure, timeout=srv_timeout_sec)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)

    # Add OTEL to requests library instrumentation
    RequestsInstrumentor().instrument()

# Callback called after app chassis loads
def __ap_chass_load() -> None:
    __activate_otel()

# Register callback to activate OTEL when chassis loads
AppChassis.register_global_dependency_callback(__ap_chass_load)
__activate_otel()  # in case chassis is already loaded
# end.