from .exceptions import SigaaConnectionError
import re
class Course:
    def __init__(self, session, title, form_data):
        self.session = session
        self.title = title
        self.form_data = form_data
        self.id = form_data['post_values'].get('idTurma')
        self.grades = []
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
        data = {
            'total_faltas': 0,
            'max_faltas': 0,
            'percent': 0.0
        }
        text_content = page.soup.get_text()
        total_match = re.search(r'Total de Faltas:\s*(\d+)', text_content)
        if total_match:
            data['total_faltas'] = int(total_match.group(1))
        max_match = re.search(r'Máximo de Faltas Permitido:\s*(\d+)', text_content)
        if max_match:
            data['max_faltas'] = int(max_match.group(1))
        if data['max_faltas'] > 0:
            total_classes = data['max_faltas'] * 4
            data['percent'] = (data['total_faltas'] / total_classes) * 100
        else:
            data['percent'] = 0.0
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
