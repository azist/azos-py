from azos.chassis import AppChassis
from azos.db.pgconnector import PgSqlCtreeChassisDescriptorFactory, PgConnector
from azos.sky.ctree import ConfigTree

app = AppChassis("gov", __file__, descriptor_factory=PgSqlCtreeChassisDescriptorFactory())

print(app.descriptor.data)

app.deps.register(PgConnector, app.make_configured(PgConnector, "pg-connector", default_type_name="PgConnector"))
app.deps.register(ConfigTree, app.make_specific(ConfigTree, "ctree"))


