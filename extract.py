import re
import os
filepath = 'c:\\Users\\alcoh\\PycharmProjects\\boletim_sigaa\\app\\templates\\dashboard.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
style_pattern = re.compile('<style>(.*?)</style>', re.DOTALL | re.IGNORECASE)
style_match = style_pattern.search(content)
if style_match:
    css_content = style_match.group(1).strip()
    with open('c:\\Users\\alcoh\\PycharmProjects\\boletim_sigaa\\app\\static\\dashboard.css', 'w', encoding='utf-8') as f:
        f.write(css_content)
    content = content[:style_match.start()] + '<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'dashboard.css\') }}">\n' + content[style_match.end():]
script_blocks = list(re.finditer('<script>(.*?)</script>', content, re.DOTALL | re.IGNORECASE))
if script_blocks:
    last_script = script_blocks[-1]
    js_content = last_script.group(1).strip()
    js_content = js_content.replace("{{ session['username']|default ('guest') | tojson }}", 'window.APP_CONFIG.currentUser')
    js_content = js_content.replace("{{ url_for('main.activate_account', id=999999) }}", 'window.APP_CONFIG.urls.activateAccount')
    js_content = js_content.replace('{{ csrf_token() }}', 'window.APP_CONFIG.csrfToken')
    with open('c:\\Users\\alcoh\\PycharmProjects\\boletim_sigaa\\app\\static\\dashboard.js', 'w', encoding='utf-8') as f:
        f.write(js_content)
    config_script = '<script>\n    window.APP_CONFIG = {\n        csrfToken: "{{ csrf_token() }}",\n        currentUser: {{ session[\'username\']|default(\'guest\')|tojson }},\n        urls: {\n            activateAccount: "{{ url_for(\'main.activate_account\', id=999999) }}"\n        }\n    };\n    </script>\n    <script src="{{ url_for(\'static\', filename=\'dashboard.js\') }}"></script>'
    content = content[:last_script.start()] + config_script + content[last_script.end():]
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Extraction complete!')