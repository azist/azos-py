# This is a manual test app which tests APM from CLI interace
import traceback

# Bootsrap the application chassis
from azos import chassis
chassis.AppChassis("toy-apm-cli", __file__)

from azos.apm.log import LogStrand
import azos.apm.otel


log = LogStrand("app body", rel="self")
log.info("Starting toy-apm-cli app...")
log.debug("This is a debug message", extra={"a": 1, "b": 2, "C": [1,2,3]})

for x in range(3):
    log.debug(f"Loop iteration {x+1}", extra={"iteration": x+1})


try:
    1 / 0
except Exception as error:
    log.error("Exception With exc_info", exc_info=True)

    tb = traceback.format_exc()
    log.error("Exception With Traceback", extra={"error": tb})

log.info("Appfinished")
