from app.sigaa_api.enums import InstitutionType
from .calculators import AcademicCalculator, IFAcademicCalculator, UFAcademicCalculator
class CalculatorFactory:
    @staticmethod
    def get_calculator(institution: InstitutionType) -> AcademicCalculator:
        if institution == InstitutionType.UFAL:
            return UFAcademicCalculator()
        elif institution == InstitutionType.UFPE:
            return UFAcademicCalculator()
        elif institution == InstitutionType.IFAL:
            return IFAcademicCalculator()
        else:
            return IFAcademicCalculator()
