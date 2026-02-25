from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Union, Dict, Any
class GradeType(Enum):
    SINGLE = "single"
    GROUP = "group"
@dataclass
class Grade:
    name: str
    value: Optional[float] = None
    weight: float = 1.0
    type: GradeType = GradeType.SINGLE
    children: List['Grade'] = field(default_factory=list)
    def to_dict(self):
        d = {
            "name": self.name,
            "value": self.value,
            "weight": self.weight,
            "type": self.type.value
        }
        if self.children:
            d["children"] = [child.to_dict() for child in self.children]
        return d
class CourseStatus(Enum):
    APPROVED = "Aprovado"
    FAILED = "Reprovado"
    FINAL_EXAM = "Prova Final"
    IN_PROGRESS = "Cursando"
    RECOVERY = "Recuperação"
    UNDEFINED = "Indefinido"
@dataclass
class CourseResult:
    status: CourseStatus
    average: float
    needed: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    is_critical: bool = False
    def to_dict(self):
        return {
            "status": self.status.value,
            "average": self.average,
            "needed": self.needed,
            "details": self.details,
            "message": self.message,
            "is_critical": self.is_critical
        }
