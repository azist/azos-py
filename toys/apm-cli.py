# This is a manual test app which tests APM from CLI interace

from azos import chassis
from azos.apm.log import LogStrand
import azos.apm.otel


# Bootsrap the application chassis
chassis.AppChassis("toy-apm-cli", __file__)
log = LogStrand("app body")

log.info("Starting toy-apm-cli app...")



log.info("Appfinished")
