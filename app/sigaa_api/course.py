from .exceptions import SigaaConnectionError
from .schedule_parser import parse_schedule_code
import re

class Course:
    def __init__(self, session, title, form_data, schedule_code: str = ''):
        self.session = session
        self.title = title
        self.form_data = form_data
        self.id = form_data['post_values'].get('idTurma')
        self.grades = []
        self.schedule_code = schedule_code  # e.g. "2N1234", "4T6 4N1234"
        self.professor_name = None

    def __repr__(self):
        return f"<Course title='{self.title}'>"

    async def get_grades(self):
        course_page = await self._enter_course()
        grades_page = await self._navigate_to_grades(course_page)
        self.grades = self._parse_grades(grades_page)
        return self.grades

    async def get_frequency(self):
        course_page = await self._enter_course()
        freq_page = await self._navigate_to_frequency(course_page)
        self.frequency = self._parse_frequency(freq_page)
        return self.frequency

    async def get_grades_and_frequency(self):
        course_page = await self._enter_course()
        
        try:
            grades_page = await self._navigate_to_grades(course_page)
            self.grades = self._parse_grades(grades_page)
        except Exception:
            self.grades = []
            
        try:
            freq_page = await self._navigate_to_frequency(course_page)
            self.frequency = self._parse_frequency(freq_page)
        except Exception:
            # Fallback in case of ViewState issues
            try:
                course_page = await self._enter_course()
                freq_page = await self._navigate_to_frequency(course_page)
                self.frequency = self._parse_frequency(freq_page)
            except Exception:
                self.frequency = None
                
        return self.grades, self.frequency

    async def get_professor(self):
        course_page = await self._enter_course()
        try:
            menu_items = course_page.soup.find_all(string=re.compile(r"Participantes", re.I))
            participantes_page = None
            for item in menu_items:
                parent = item.parent
                while parent:
                    if parent.name in ['td', 'div', 'a', 'tr', 'li', 'span'] and parent.get('onclick'):
                        js_code = parent['onclick']
                        form_data = course_page.parse_jsfcljs(js_code)
                        participantes_page = await self.session.post(
                            form_data['action'],
                            data=form_data['post_values']
                        )
                        break
                    parent = parent.parent
                    if not parent or parent.name == 'body':
                        break
                if participantes_page:
                    break
            
            if participantes_page:
                # Look for <legend> containing 'Docente' or 'Professor'
                legends = participantes_page.soup.find_all('legend')
                for legend in legends:
                    txt_leg = legend.get_text(strip=True).upper()
                    if 'DOCENTE' in txt_leg or 'PROFESSOR' in txt_leg:
                        table = legend.find_next('table')
                        if table:
                            for row in table.find_all('tr'):
                                name_tag = row.find('strong')
                                if not name_tag:
                                    name_tag = row.find('a', title=re.compile(r"docente", re.I))
                                if name_tag:
                                    ct = name_tag.get_text(strip=True)
                                    if ct and len(ct) > 3:
                                        self.professor_name = ct.strip()
                                        return self.professor_name

                # Fallback to older inline method
                for cell in participantes_page.soup.find_all('td'):
                    txt = cell.get_text(strip=True).upper()
                    if 'DOCENTE' in txt or 'PROFESSOR' in txt:
                        row = cell.find_parent('tr')
                        if row:
                            row_cells = row.find_all('td')
                            for c in row_cells:
                                ct = c.get_text(strip=True)
                                ct_up = ct.upper()
                                if ct and ct_up not in ['DOCENTE', 'PROFESSOR'] and len(ct) > 3 and '@' not in ct:
                                    self.professor_name = ct.strip()
                                    return self.professor_name
        except Exception as e:
            pass
        self.professor_name = "Desconhecido"
        return self.professor_name

    async def _enter_course(self):
        page = await self.session.post(
            self.form_data['action'],
            data=self.form_data['post_values']
        )
        return page

    async def _navigate_to_grades(self, course_page):
        menu_items = course_page.soup.find_all(string="Ver Notas")
        for item in menu_items:
            parent = item.parent
            while parent:
                if parent.name in ['td', 'div', 'a']:
                    if parent.get('onclick'):
                        js_code = parent['onclick']
                        form_data = course_page.parse_jsfcljs(js_code)
                        return await self.session.post(
                            form_data['action'],
                            data=form_data['post_values']
                        )
                parent = parent.parent
                if not parent or parent.name == 'body':
                    break
        raise ValueError("Could not find 'Ver Notas' menu item.")

    async def _navigate_to_frequency(self, course_page):
        menu_items = course_page.soup.find_all(lambda text: text and "Frequência" in text)
        if not menu_items:
             menu_items = course_page.soup.find_all(lambda text: text and "Frequencia" in text)
        for item in menu_items:
            parent = item.parent
            while parent:
                if parent.name in ['td', 'div', 'a']:
                    if parent.get('onclick'):
                        js_code = parent['onclick']
                        form_data = course_page.parse_jsfcljs(js_code)
                        return await self.session.post(
                            form_data['action'],
                            data=form_data['post_values']
                        )
                parent = parent.parent
                if not parent or parent.name == 'body':
                    break
        raise ValueError("Could not find 'Frequência' menu item.")

    def _parse_frequency(self, page):
        """
        Parse the Mapa de Frequências page, row by row.

        Each row has a date and a status:
          - "Presente"        → student attended (multiply by aulas_per_session)
          - "X Falta(s)"      → X already counts individual aula slots (no extra multiply)
          - "Não Registrada"  → professor did not submit attendance (yellow zone)

        Also extracts "Aulas (Ministradas/Total): X / Y" for the real denominator.
        Falls back gracefully to summary-text parsing when the individual table is absent.
        """
        aulas_per_session = parse_schedule_code(self.schedule_code)
        text_full = page.soup.get_text()
 
        # ── 1. "Aulas (Ministradas/Total): X / Y" (Parsed early for inference fallback) ────────────────
        min_total_match = re.search(
            r'Aulas\s*\(Ministradas/Total\)\s*[:\-]?\s*(\d+)\s*/\s*(\d+)',
            text_full, re.IGNORECASE
        )
        aulas_ministradas = int(min_total_match.group(1)) if min_total_match else None
        aulas_total = int(min_total_match.group(2)) if min_total_match else None
 
        # Try to infer aulas_per_session from lack/absence records or by dividing aulas_ministradas by rows
        inferred_aulas_per_session = None
        for tbl in page.soup.find_all('table'):
            headers = [th.get_text(strip=True).lower() for th in tbl.find_all('th')]
            if any('data' in h for h in headers) and any('situa' in h for h in headers):
                num_data_rows = 0
                for row in tbl.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) < 2:
                        continue
                    num_data_rows += 1
                    status_text = cells[-1].get_text(strip=True).lower()
                    if 'falta' in status_text:
                        falta_num = re.search(r'(\d+)', status_text)
                        if falta_num:
                            inferred_aulas_per_session = int(falta_num.group(1))
 
                # Fallback: divide aulas_ministradas by number of rows in the table
                if not inferred_aulas_per_session and aulas_ministradas and num_data_rows > 0:
                    val = round(aulas_ministradas / num_data_rows)
                    if val > 0:
                        inferred_aulas_per_session = val
                break
 
        if inferred_aulas_per_session:
            aulas_per_session = inferred_aulas_per_session
 
        # ── 0. Early-exit: frequency not yet released ───────────────────────
        if 'frequência ainda não foi lançada' in text_full.lower() or \
           'frequencia ainda nao foi lancada' in text_full.lower():
            return {'nao_lancada': True}
 
        data = {
            'total_faltas':      0,
            'max_faltas':        0,
            'percent':           0.0,
            'presencas':         0,
            'ausencias':         0,
            'nao_registradas':   0,
            'aulas_ministradas': aulas_ministradas,
            'aulas_total':       aulas_total,
            'logs':              [],
            'aulas_per_session': aulas_per_session,
        }
 
        # ── 2. Individual date rows ─────────────────────────────────────────
        freq_table = None
        for tbl in page.soup.find_all('table'):
            # Look for a table whose headers contain Data / Situação
            headers = [th.get_text(strip=True).lower() for th in tbl.find_all('th')]
            if any('data' in h for h in headers) and any('situa' in h for h in headers):
                freq_table = tbl
                break

        if freq_table:
            rows = freq_table.find_all('tr')
            presencas_count = 0
            ausencias_aulas = 0
            nao_reg_count   = 0
            logs = []

            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                date_text = cells[0].get_text(strip=True)
                status_raw = cells[-1].get_text(strip=True)
                status_text = status_raw.lower()

                if 'presente' in status_text:
                    presencas_count += 1
                    logs.append({
                        'date': date_text,
                        'status': 'Presente',
                        'value': aulas_per_session
                    })
                elif 'falta' in status_text:
                    falta_num = re.search(r'(\d+)', status_text)
                    val = int(falta_num.group(1)) if falta_num else aulas_per_session
                    ausencias_aulas += val
                    logs.append({
                        'date': date_text,
                        'status': 'Ausente',
                        'value': val
                    })
                elif 'não registrada' in status_text or 'nao registrada' in status_text:
                    nao_reg_count += 1
                    logs.append({
                        'date': date_text,
                        'status': 'Pendente',
                        'value': aulas_per_session
                    })

            data['presencas']       = presencas_count * aulas_per_session
            data['ausencias']       = ausencias_aulas
            data['total_faltas']    = ausencias_aulas
            data['nao_registradas'] = nao_reg_count * aulas_per_session
            data['logs']            = logs

            # ── 3. max_faltas and percent ───────────────────────────────────
            total_ref = data['aulas_total'] or 0
            if total_ref == 0:
                # Fallback: infer from max_faltas text
                max_m = re.search(r'Máximo de Faltas Permitido:\s*(\d+)', text_full)
                if max_m:
                    data['max_faltas'] = int(max_m.group(1))
                    total_ref = data['max_faltas'] * 4
                else:
                    data['max_faltas'] = 0
            else:
                data['max_faltas'] = int(total_ref * 0.25)

            if total_ref > 0:
                data['percent'] = (data['total_faltas'] / total_ref) * 100.0

            return data

        # ── 4. Fallback: summary-text parsing (old behaviour) ───────────────
        total_match = re.search(r'Total de Faltas:\s*(\d+)', text_full)
        if total_match:
            data['total_faltas'] = int(total_match.group(1))
            data['ausencias']    = data['total_faltas']
            max_m = re.search(r'Máximo de Faltas Permitido:\s*(\d+)', text_full)
            if max_m:
                data['max_faltas'] = int(max_m.group(1))
                total_classes = data['max_faltas'] * 4
                data['aulas_total'] = total_classes
                if total_classes > 0:
                    data['percent'] = (data['total_faltas'] / total_classes) * 100
            return data

        # UFAL summary
        presencas_m   = re.search(r'Presenças Registradas:\s*(\d+)', text_full)
        aulas_reg_m   = re.search(r'Número de Aulas com Registro de Frequência:\s*(\d+)', text_full)
        ch_m          = re.search(r'Número de Aulas definidas pela CH do Componente:\s*(\d+)', text_full)
        if presencas_m and aulas_reg_m and ch_m:
            presencas      = int(presencas_m.group(1))
            aulas_reg      = int(aulas_reg_m.group(1))
            ch             = int(ch_m.group(1))
            data['total_faltas']    = aulas_reg - presencas
            data['max_faltas']      = int(ch * 0.25)
            data['presencas']       = presencas
            data['ausencias']       = data['total_faltas']
            data['nao_registradas'] = max(0, ch - aulas_reg)
            data['aulas_total']     = ch
            data['aulas_ministradas'] = aulas_reg
            if ch > 0:
                data['percent'] = (data['total_faltas'] / ch) * 100.0
        return data

    def _parse_grades(self, page):
        """
        Parses the grades table generically, extracting all columns not in the ignore list.
        Returns a structure compatible with the Domain Grade model.
        """
        grades = []
        table = page.soup.find('table', class_='tabelaRelatorio')
        if not table:
            return []
        thead = table.find('thead')
        tbody = table.find('tbody')
        if not thead or not tbody:
            return []
        header_rows = thead.find_all('tr')
        if not header_rows:
            return []
        main_headers = header_rows[0].find_all('th')
        sub_headers_row = header_rows[1] if len(header_rows) > 1 else None

        # Build queue of non-empty subheaders
        sub_headers_queue = []
        if sub_headers_row:
            all_sub_headers = sub_headers_row.find_all('th')
            for sh in all_sub_headers:
                text = sh.get_text(strip=True)
                if text:
                    sub_headers_queue.append({
                        'text': text,
                        'id': sh.get('id', '')
                    })

        # Pre-calculate column mapping based on Main Headers logic to skip ghost headers
        col_to_subheader = {}
        sh_ptr = 0
        current_map_col = 0
        ignore_names = ['', 'Matrícula', 'Nome', 'Sit.', 'Faltas', 'Resultado', 'Situação']
        single_grade_names = ['Reposição', 'Recuperação']

        for header in main_headers:
            header_text = header.get_text(strip=True)
            colspan = int(header.get('colspan') or 1)

            # Matrícula, Nome, etc. OR single grade columns (Reposição)
            # usually don't have subheaders (or have empty ones in Row 2)
            # so we assume they don't consume from the queue.
            if header_text in ignore_names or (header_text in single_grade_names and colspan == 1):
                current_map_col += colspan
                continue

            # For Group Headers (Units, etc.), we consume `colspan` items from the queue
            # This handles cases where Row 2 has extra empty headers for Reposição/etc.
            for _ in range(colspan):
                if sh_ptr < len(sub_headers_queue):
                    col_to_subheader[current_map_col] = sub_headers_queue[sh_ptr]
                    sh_ptr += 1
                current_map_col += 1

        student_row = None
        for row in tbody.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) > 1:
                name_cell = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                if len(name_cell) > 10 and any(c.isalpha() for c in name_cell):
                    student_row = row
                    break
        if not student_row:
            return []
        value_cells = student_row.find_all('td')
        current_cell_idx = 0

        for i, header in enumerate(main_headers):
            header_text = header.get_text(strip=True)
            colspan = int(header.get('colspan') or 1)

            if header_text in ignore_names:
                current_cell_idx += colspan
                continue

            group_name = header_text

            if colspan == 1:
                if current_cell_idx < len(value_cells):
                    val_text = value_cells[current_cell_idx].get_text(strip=True)
                    val = self._parse_float(val_text)
                    if val is not None or val_text not in ['', '-', '--', 'S/N']:
                        grades.append({
                            'name': group_name,
                            'value': val,
                            'type': 'single'
                        })
                current_cell_idx += 1
            else:
                sub_grades = []
                for j in range(colspan):
                    cell_idx = current_cell_idx + j
                    if cell_idx >= len(value_cells):
                        break

                    val_text = value_cells[cell_idx].get_text(strip=True)
                    val = self._parse_float(val_text)

                    sub_name = "Nota"
                    if cell_idx in col_to_subheader:
                        mapped = col_to_subheader[cell_idx]
                        sub_name = mapped['text']
                        sub_id = mapped['id']
                        if sub_id and sub_id.startswith('aval_'):
                            grade_id = sub_id[5:]
                            name_input = page.soup.find('input', id=f'denAval_{grade_id}')
                            if name_input and name_input.get('value'):
                                sub_name = name_input.get('value')

                    if val_text:
                        sub_grades.append({
                            'name': sub_name,
                            'value': val
                        })
                if sub_grades:
                    grades.append({
                        'name': group_name,
                        'type': 'group',
                        'grades': sub_grades
                    })
                current_cell_idx += colspan
        return grades
    def _parse_float(self, text):
        """
        Parse a string to float, handling Brazilian decimal format.
        Returns None if parsing fails or text is empty/dash.
        """
        if not text or text in ['-', '--', 'S/N', '']:
            return None
        text = text.strip()
        try:
            return float(text.replace(',', '.'))
        except ValueError:
            return None
