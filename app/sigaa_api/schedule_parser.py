"""
Parser for SIGAA schedule codes.

Format: one or more groups separated by spaces.
Each group: D T S...
  D  = weekday digit (1=Sun, 2=Mon, 3=Tue, 4=Wed, 5=Thu, 6=Fri, 7=Sat)
  T  = shift letter: M (Manhã), T (Tarde), N (Noite)
  S+ = one or more slot digits (each digit = one 50-min class slot)

Examples:
  "2N1234"    -> 1 group, 4 slots  -> 4 aulas per session
  "4T6 4N1234"-> 2 groups (1+4)    -> 5 aulas per session
  "4N12"      -> 1 group, 2 slots  -> 2 aulas per session
  "6T1"       -> 1 group, 1 slot   -> 1 aula per session
  "2M34"      -> 1 group, 2 slots  -> 2 aulas per session
"""

import re

# Regex for a single schedule group: day digit + M/T/N + one or more slot digits
_GROUP_RE = re.compile(r'\d[MTN]\d+', re.IGNORECASE)


def parse_schedule_code(code: str) -> int:
    """
    Return the total number of 50-min aula slots per class day.

    For multi-group codes (e.g. "4T6 4N1234") the groups are assumed to
    fall on the SAME weekday, so their slot counts are summed.

    Returns 1 as a safe default if the code cannot be parsed.
    """
    if not code:
        return 1
    code = code.strip()
    groups = _GROUP_RE.findall(code)
    if not groups:
        return 1
    total_slots = 0
    for group in groups:
        # Slots are all characters after the shift letter (index 2 onward)
        slots = group[2:]
        total_slots += len(slots)
    return max(1, total_slots)
