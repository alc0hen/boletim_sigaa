import sys
from bs4 import BeautifulSoup

with open(r'C:\Users\alcoh\PycharmProjects\sigaa_api_python\paginas_sigaa\IFAL\perfil_diciplina.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()
    
soup = BeautifulSoup(html, 'html.parser')
for el in soup.find_all(['td', 'a', 'div', 'li', 'span', 'button']):
    text = el.get_text(strip=True).lower()
    title = (el.get('title') or '').lower()
    if 'frequ' in text or 'nota' in text or 'falta' in text or 'frequ' in title or 'nota' in title or 'falta' in title:
        print(f'TAG: {el.name}')
        print(f'CLASS: {el.get("class")}')
        print(f'ID: {el.get("id")}')
        print(f'ONCLICK: {el.get("onclick")}')
        print(f'HREF: {el.get("href")}')
        print(f'TITLE: {el.get("title")}')
        print(f'TEXT: {el.get_text(strip=True)}')
        print("-" * 40)
