from __future__ import annotations
from .config import D2Config
from .db import D2Database
from .audit import AuditService
from .integrity import IntegrityService
from .intake import IntakeService
from .derivatives import DerivativeService
from .metadata import MetadataService
from .export import ExportService

class D2Services:
    def __init__(self,config=None):
        self.config=config or D2Config.from_env();self.config.ensure();self.database=D2Database(self.config.database);self.audit=AuditService(self.database);self.integrity=IntegrityService(self.database,self.audit);self.intake=IntakeService(self.config,self.database,self.audit);self.derivatives=DerivativeService(self.config,self.database,self.audit,self.integrity);self.metadata=MetadataService(self.database,self.audit,self.intake);self.exports=ExportService(self.config,self.database,self.audit,self.intake,self.integrity,self.derivatives)
