from azos.chassis import AppChassis
from azos.db.pgconnector import PgSqlCtreeChassisDescriptorFactory

app = AppChassis("gov", __file__, descriptor_factory=PgSqlCtreeChassisDescriptorFactory())

print(app.descriptor.data)

