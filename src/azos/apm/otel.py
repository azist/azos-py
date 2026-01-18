"""
Azos Open Telemetry Module
Copyright (C) 2026 Azist, MIT License
"""
from . import log
from azos.chassis import AppChassis

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider, Tracer, StatusCode
    from opentelemetry.sdk.trace.export import (BatchSpanProcessor,
                                                SpanExporter,
                                                ConsoleSpanExporter,
                                                SimpleSpanProcessor,
                                                SpanExportResult)
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
except ImportError as cause:
    raise ImportError(
        "Azos APM Open Telemetry module requires opentelemetry-sdk and related packages. "
        "Please install them via pip: " \
        " pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp") from cause


# Enriches our logs with OTEL cross correlation tokens
# this gets wired up into logging so you don't need to call this ever
def log_otel_enricher(fmt, record, log_data):
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()
    trace_id = span_context.trace_id  # Integer
    span_id = span_context.span_id    # Integer
    if trace_id != 0: log_data["oti"] = trace.format_trace_id(trace_id)
    if span_id != 0: log_data["ots"] = trace.format_span_id(span_id)


# Patch-in the hook to enrich our logs with OTEL info
log.AzLogRecordFormatter._hook_enrichment_func = log_otel_enricher


########################################
###### Enable OTEL for Our App #########
########################################
# Assuming OTLP exporter
trace.set_tracer_provider(TracerProvider())

# Use it like this
# tracer = trace.get_tracer(__name__)
# with tracer.start_as_current_span("parent-operation") as parent:
#     with tracer.start_as_current_span("child-operation"):
#         # Your code here
