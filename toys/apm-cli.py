# This is a manual test app which tests APM from CLI interace
import traceback

# Bootsrap the application chassis
from azos import chassis
chassis.AppChassis("toy-apm-cli", __file__)

from azos.apm.log import LogStrand
from azos.apm.otel import get_tracer


log = LogStrand("app.body", rel="self")
log.info("Starting toy-apm-cli app...")
log.debug("This is a debug message", extra={"a": 1, "b": 2, "C": [1,2,3]})

log.info("""This is a large text block which spans multiple lines.
It is used to test how well the logging system handles
multi-line messages. Each line should be properly indented
and formatted to ensure readability in the logs.
This helps in debugging and understanding the flow of the application.
End of the large text block.""")

log.warning("Warning now")
log.error("A simple error text")
log.critical("Critical catastrophic event")

log.info("This message will be in the oplog channel", extra={"sys_channel": "oplog"})

oplog = LogStrand("app.oplog", rel="self", channel="oplog")

oplog.info("Starting a loop")
for x in range(3):
    oplog.debug(f"Loop iteration {x+1}", extra={"iteration": x+1})


try:
    1 / 0
except Exception as error:
    log.error("Exception With exc_info", exc_info=True)

    tb = traceback.format_exc()
    log.error("Exception With Traceback", extra={"error": tb})

# OpenTelemetry example: outer and inner spans with logging in each
tracer = get_tracer(__name__)

with tracer.start_as_current_span("outer-operation") as outer_span:
    log.info("Entered outer span", extra={"otel_span": "outer-operation"})
    outer_span.set_attribute("example.role", "outer")

    with tracer.start_as_current_span("inner-operation") as inner_span:
        log.info("Entered inner span", extra={"otel_span": "inner-operation"})
        inner_span.set_attribute("example.role", "inner")
        # simulate some work inside inner span
        for i in range(2):
            log.debug(f"inner work step {i}", extra={"step": i})

    log.info("Exited inner span, back in outer span", extra={"otel_span": "outer-operation"})

log.info("Appfinished")
