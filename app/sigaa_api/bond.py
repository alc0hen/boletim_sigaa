from urllib.parse import urljoin
from .exceptions import SigaaConnectionError
from .course import Course
import re
import logging
logger = logging.getLogger(__name__)
class StudentBond:
    def __init__(self, session, registration, program, switch_url=None):
        self.session = session
        self.registration = registration
        self.program = program
        self.switch_url = switch_url
        self.courses = []
    async def get_courses(self):
        page = None
        if self.switch_url:
             page = await self.session.get(self.switch_url)
        else:
             page = await self.session.get('/sigaa/portais/discente/discente.jsf')
        self.courses = self._parse_courses(page)
        return self.courses
    def _parse_courses(self, page):
        courses = []
        try:
            tables = page.soup.find_all('table')
            for table in tables:
                headers = table.find_all('th')
                header_texts = [h.get_text(strip=True) for h in headers]
                is_course_table = any('Componente' in h or 'Disciplina' in h for h in header_texts)
                title_idx = -1
                for i, h in enumerate(header_texts):
                    if 'Componente' in h or 'Disciplina' in h:
                        title_idx = i
                        break
                if not is_course_table:
                    first_row = table.find('tr')
                    if first_row:
                        row_text = first_row.get_text(strip=True)
                        if 'Componente' in row_text or 'Disciplina' in row_text:
                             is_course_table = True
                if not is_course_table:
                    continue
                tbody = table.find('tbody')
                rows = tbody.find_all('tr') if tbody else table.find_all('tr')
                for row in rows:
                    if 'periodo' in row.get('class', []): continue
                    row_text_clean = row.get_text(strip=True)
                    if 'Componente Curricular' in row_text_clean or 'Disciplina' in row_text_clean:
                        continue
                    cells = row.find_all('td')
                    if not cells: continue
                    name_cell = None
                    if title_idx != -1 and title_idx < len(cells):
                        name_cell = cells[title_idx]
                    if not name_cell:
                        for cell in cells:
                            if cell.find('span', class_='tituloDisciplina'):
                                name_cell = cell
                                break
                    if not name_cell and len(cells) > 1:
                         if title_idx == -1:
                             text1 = cells[1].get_text(strip=True)
                             if "Campus" in text1 or "Sala" in text1:
                                 name_cell = cells[0]
                             else:
                                 name_cell = cells[1]
                    if not name_cell: continue
                    if name_cell.find('span', class_='tituloDisciplina'):
                        title = name_cell.find('span', class_='tituloDisciplina').get_text(strip=True)
                    else:
                        title = name_cell.get_text(strip=True)
                    access_link = row.find('a', onclick=True)
                    if not access_link:
                        for cell in cells:
                             link = cell.find('a', onclick=True)
                             if link and ('discente' in str(link.get('title', '')).lower() or 'acessar' in link.get_text(strip=True).lower()):
                                 access_link = link
                                 break
                    if access_link:
                        js_code = access_link['onclick']
                        try:
                            form_data = page.parse_jsfcljs(js_code)
                            courses.append(Course(self.session, title, form_data))
                        except Exception: pass
        except Exception as e:
            logger.error(f"Error parsing courses: {e}")
        return courses
    async def get_history(self):
        try:
            page = None
            if self.switch_url:
                page = await self.session.get(self.switch_url)
            else:
                page = await self.session.get('/sigaa/portais/discente/discente.jsf')
            form_data = self._extract_jscook_action(page, 'Boletim')
            bulletin_page = None
            if form_data:
                bulletin_page = await self.session.post(form_data['action_url'], data=form_data['post_values'])
            else:
                link = page.soup.find('a', string=re.compile(r"Boletim", re.I))
                if not link: link = page.soup.find('a', title='Boletim')
                if link:
                    if link.get('onclick'):
                         js = page.parse_jsfcljs(link['onclick'])
                         bulletin_page = await self.session.post(js['action'], data=js['post_values'])
                    else:
                         href = link.get('href')
                         if href and href != '#':
                             bulletin_page = await self.session.get(urljoin(str(page.url), href))
            if not bulletin_page:
                form_data = self._extract_jscook_action(page, 'Consultar Minhas Notas')
                if form_data:
                    bulletin_page = await self.session.post(form_data['action_url'], data=form_data['post_values'])
            if not bulletin_page:
                link = page.soup.find('a', string=re.compile(r"Consultar\s.*Notas", re.I))
                if not link: link = page.soup.find('a', title='Consultar Notas')
                if link:
                    if link.get('onclick'):
                         js = page.parse_jsfcljs(link['onclick'])
                         bulletin_page = await self.session.post(js['action'], data=js['post_values'])
                    else:
                         href = link.get('href')
                         if href and href != '#':
                             bulletin_page = await self.session.get(urljoin(str(page.url), href))
            if bulletin_page:
                return self._parse_bulletin(bulletin_page)
            return {}
        except Exception as e:
            logger.error(f"Get history error: {e}")
            return {}
    def _extract_jscook_action(self, page, label):
        try:
            form = page.soup.find('form', id=re.compile(r'menu:form_menu_discente|menuForm'))
            if not form:
                 form = page.soup.find('input', attrs={'name': 'jscook_action'})
                 if form: form = form.find_parent('form')
            if not form: return None
            post_values = {}
            for inp in form.find_all('input'):
                if inp.get('name'): post_values[inp.get('name')] = inp.get('value', '')
            scripts = page.soup.find_all('script')
            action = None
            for s in scripts:
                if s.string and (f"'{label}'" in s.string or f'"{label}"' in s.string):
                    matches = re.findall(fr"['\"]{label}['\"]\s*,\s*['\"]([^'\"]+)['\"]", s.string)
                    if matches:
                        action = matches[0]
                        break
            if action:
                post_values['jscook_action'] = action
                url = form.get('action')
                return {'action_url': urljoin(str(page.url), url), 'post_values': post_values}
        except: pass
        return None
    def _parse_bulletin(self, page):
        history = {}
        try:
            tables = page.soup.find_all('table', class_='tabelaRelatorio')
            for table in tables:
                caption = table.find('caption')
                semester = caption.get_text(strip=True) if caption else "Unknown"
                subjects = []
                rows = table.find_all('tr')
                headers_row = table.find('th').parent if table.find('th') else None
                if not headers_row: continue
                headers = [th.get_text(strip=True).lower() for th in headers_row.find_all('th')]
                idx_name = -1
                idx_final_grade = -1
                idx_status = -1
                idx_absences = -1
                for i, h in enumerate(headers):
                    h_lower = h.lower()
                    if 'componente' in h_lower or 'disciplina' in h_lower: idx_name = i
                    elif 'situação' in h_lower or 'status' in h_lower: idx_status = i
                    elif 'faltas' in h_lower: idx_absences = i
                    elif 'resultado' in h_lower or 'média' in h_lower or 'nota' in h_lower:
                        idx_final_grade = i
                grade_indices = []
                for i, h in enumerate(headers):
                     if i == idx_name or i == idx_status or i == idx_absences: continue
                     if i == idx_final_grade and ('resultado' in h.lower() or 'média' in h.lower() or 'nota final' in h.lower()): continue
                     h_lower = h.lower()
                     if h_lower in ['créditos', 'ch', 'turma', 'tipo', 'código', 'ano', 'período']: continue
                     grade_indices.append((i, h))
                if idx_name == -1: continue
                for row in rows:
                    if 'class' in row.attrs and ('agrupador' in row['class'] or 'titulo' in row['class']): continue
                    cells = row.find_all('td')
                    if not cells: continue
                    try:
                        if idx_name >= len(cells): continue
                        name = cells[idx_name].get_text(strip=True)
                        status = cells[idx_status].get_text(strip=True) if idx_status != -1 and idx_status < len(cells) else ""
                        final_grade = None
                        if idx_final_grade != -1 and idx_final_grade < len(cells):
                            txt = cells[idx_final_grade].get_text(strip=True).replace(',', '.')
                            if txt and txt != '-' and txt != '--':
                                try: final_grade = float(txt)
                                except: pass
                        absences = 0
                        if idx_absences != -1 and idx_absences < len(cells):
                            txt = cells[idx_absences].get_text(strip=True)
                            try: absences = int(txt)
                            except: pass
                        detailed_grades = []
                        for idx, label in grade_indices:
                            if idx < len(cells):
                                val_txt = cells[idx].get_text(strip=True).replace(',', '.')
                                if val_txt and val_txt != '-' and val_txt != '--':
                                    try:
                                        val = float(val_txt)
                                        detailed_grades.append({'name': label, 'value': val})
                                    except: pass
                        subjects.append({
                            "name": name,
                            "final_grade": final_grade,
                            "absences": absences,
                            "status": status,
                            "grades": detailed_grades
                        })
                    except: continue
                if subjects:
                    history[semester] = subjects
        except Exception as e:
            logger.error(f"Parse bulletin error: {e}")
        return history
    def __repr__(self):
        return f"<StudentBond registration='{self.registration}' program='{self.program}'>"
class TeacherBond:
    def __repr__(self):
        return "<TeacherBond>"
