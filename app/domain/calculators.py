from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .models import Grade, CourseStatus, CourseResult, GradeType
class AcademicCalculator(ABC):
    @abstractmethod
    def calculate(self, grades: List[Dict[str, Any]]) -> CourseResult:
        pass
    def _get_grade_value(self, grades: List[Dict[str, Any]], name_hints: List[str]) -> Optional[float]:
        for hint in name_hints:
            hint_lower = hint.lower()
            for g in grades:
                g_name = g.get('name', '').lower()
                if hint_lower in g_name or g_name in hint_lower:
                    val = g.get('value')
                    if val is not None:
                        return float(val)
                    if g.get('type') == 'group' or g.get('type') == 'group':
                        sub_grades = g.get('grades', [])
                        valid_subs = [sg['value'] for sg in sub_grades if sg.get('value') is not None]
                        if valid_subs:
                            return sum(valid_subs) / len(valid_subs)
        return None
    def _round_half(self, val: float) -> float:
        return round(val * 2) / 2
class IFAcademicCalculator(AcademicCalculator):
    def calculate(self, grades: List[Dict[str, Any]]) -> CourseResult:
        b_grades = [None] * 4
        r_grades = [None] * 2
        for g in grades:
            name = g.get('name', '').strip()
            val = None
            if g.get('type') == 'group':
                subs = [float(sg['value']) for sg in g.get('grades', []) if sg.get('value') is not None]
                if not subs:
                    val = None
                else:
                    val = subs[-1]
            elif g.get('value') is not None:
                val = float(g.get('value'))
            if val is None:
                continue
            if '1' in name and 'Unidade' in name: b_grades[0] = val
            elif '2' in name and 'Unidade' in name: b_grades[1] = val
            elif '3' in name and 'Unidade' in name: b_grades[2] = val
            elif '4' in name and 'Unidade' in name: b_grades[3] = val
            elif name == '1': b_grades[0] = val
            elif name == '2': b_grades[1] = val
            elif name == '3': b_grades[2] = val
            elif name == '4': b_grades[3] = val
            if 'Recuperação' in name or 'Reposição' in name:
                if '2' in name: r_grades[1] = val
                else:
                    if r_grades[0] is None: r_grades[0] = val
                    else: r_grades[1] = val
        b1 = b_grades[0] if b_grades[0] is not None else 0.0
        b2 = b_grades[1] if b_grades[1] is not None else 0.0
        s1_raw_sum = b1 + b2
        s1_compensated = s1_raw_sum >= 12.0
        s1_total = s1_raw_sum
        if r_grades[0] is not None:
            min_s1 = min(b1, b2)
            if r_grades[0] > min_s1:
                s1_total = s1_total - min_s1 + r_grades[0]
        b3 = b_grades[2] if b_grades[2] is not None else 0.0
        b4 = b_grades[3] if b_grades[3] is not None else 0.0
        s2_raw_sum = b3 + b4
        s2_compensated = s2_raw_sum >= 12.0
        s2_total = s2_raw_sum
        if r_grades[1] is not None:
            min_s2 = min(b3, b4)
            if r_grades[1] > min_s2:
                s2_total = s2_total - min_s2 + r_grades[1]
        total = s1_total + s2_total
        final_avg = self._round_half(total / 4)
        status = CourseStatus.IN_PROGRESS
        needed = max(0.0, 24.0 - total)
        if final_avg >= 6.0:
            status = CourseStatus.APPROVED
            needed = 0.0
        else:
             remaining_b = sum(1 for x in b_grades if x is None)
             if remaining_b == 0 and needed > 0:
                 status = CourseStatus.FAILED
        styling = {}
        def get_badge_class(grade_val, compensated):
            if grade_val is None: return "bd-info"
            if compensated:
                if grade_val >= 6.0: return "bd-ok"
                else: return "bd-warn"
            else:
                if grade_val >= 6.0: return "bd-ok"
                else: return "bd-danger"
        styling['b1_class'] = get_badge_class(b_grades[0], s1_compensated)
        styling['b2_class'] = get_badge_class(b_grades[1], s1_compensated)
        styling['b3_class'] = get_badge_class(b_grades[2], s2_compensated)
        styling['b4_class'] = get_badge_class(b_grades[3], s2_compensated)
        details = {
            "b1": b_grades[0], "b2": b_grades[1],
            "b3": b_grades[2], "b4": b_grades[3],
            "r1": r_grades[0], "r2": r_grades[1],
            "styling": styling
        }
        return CourseResult(
            status=status,
            average=final_avg,
            needed=needed,
            details=details,
            message=f"Falta {needed:.1f} pts" if needed > 0 and status != CourseStatus.FAILED else "",
            is_critical=(status == CourseStatus.FAILED)
        )
class UFAcademicCalculator(AcademicCalculator):
    def calculate(self, grades: List[Dict[str, Any]]) -> CourseResult:
        av1 = self._get_grade_value(grades, ["AV1", "1"])
        av2 = self._get_grade_value(grades, ["AV2", "2"])
        reav = self._get_grade_value(grades, ["REAVALIAÇÃO", "Reavaliação"])
        final_exam = self._get_grade_value(grades, ["PROVA FINAL", "Prova Final", "Final"])
        val_av1 = av1 if av1 is not None else 0.0
        val_av2 = av2 if av2 is not None else 0.0
        if reav is not None:
            min_av = min(val_av1, val_av2)
            if reav > min_av:
                if val_av1 == min_av: val_av1 = reav
                else: val_av2 = reav
        nf = (val_av1 + val_av2) / 2
        status = CourseStatus.IN_PROGRESS
        needed = 0.0
        message = ""
        has_av1 = av1 is not None
        has_av2 = av2 is not None
        if not (has_av1 and has_av2) and final_exam is None:
            if has_av1:
                needed_for_pass = max(0.0, 14.0 - val_av1)
                needed_for_final = max(0.0, 10.0 - val_av1)
                if needed_for_pass <= 10:
                    needed = needed_for_pass
                    message = f"Falta {needed:.1f} na AV2"
                elif needed_for_final <= 10:
                    needed = needed_for_final
                    message = f"Precisa de {needed:.1f} p/ Final"
                else:
                    message = "Reprovado matematicamente"
                    status = CourseStatus.FAILED
            else:
                 message = "Aguardando notas"
        else:
            if nf >= 7.0:
                status = CourseStatus.APPROVED
                message = "Aprovado por Média"
            elif nf < 5.0:
                status = CourseStatus.FAILED
                message = "Reprovado por Média"
            else:
                status = CourseStatus.FINAL_EXAM
                if final_exam is not None:
                    final_avg = (nf * 6 + final_exam * 4) / 10
                    if final_avg >= 5.5:
                        status = CourseStatus.APPROVED
                        message = "Aprovado na Final"
                    else:
                        status = CourseStatus.FAILED
                        message = "Reprovado na Final"
                    nf = final_avg
                else:
                    needed_final = (55 - 6 * nf) / 4
                    needed = max(0.0, needed_final)
                    message = f"Precisa de {needed:.1f} na Final"
        details = {
            "av1": av1, "av2": av2, "reav": reav, "final": final_exam, "nf": nf
        }
        return CourseResult(
            status=status,
            average=nf,
            needed=needed,
            details=details,
            message=message,
            is_critical=(status == CourseStatus.FAILED)
        )
