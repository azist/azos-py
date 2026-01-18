# This is a manual test app which tests APM from CLI interace

from azos import chassis
import azos.apm.log
import azos.apm.otel



chassis.AppChassis("toy-apm-cli", __file__)

