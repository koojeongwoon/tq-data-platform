
from .core import Step, JobContext
from services.welfare import WelfareService

class CentralWelfareStep(Step):
    def __init__(self, service: WelfareService):
        super().__init__("Central Welfare Collection")
        self.service = service

    def execute(self, context: JobContext):
        self.service.process_central_welfare()

class RegionalWelfareStep(Step):
    def __init__(self, service: WelfareService):
        super().__init__("Regional Welfare Collection")
        self.service = service

    def execute(self, context: JobContext):
        self.service.process_regional_welfare()

class NormalizationStep(Step):
    def __init__(self, service: WelfareService):
        super().__init__("Data Normalization")
        self.service = service

    def execute(self, context: JobContext):
        self.service.normalize_data()
