import re
import os

filepath = r'c:\Users\alcoh\PycharmProjects\boletim_sigaa\app\templates\dashboard.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Extract style block
style_pattern = re.compile(r'<style>(.*?)</style>', re.DOTALL | re.IGNORECASE)
style_match = style_pattern.search(content)
if style_match:
    css_content = style_match.group(1).strip()
    with open(r'c:\Users\alcoh\PycharmProjects\boletim_sigaa\app\static\dashboard.css', 'w', encoding='utf-8') as f:
        f.write(css_content)
    
    # Replace style block with link
    content = content[:style_match.start()] + '<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'dashboard.css\') }}">\n' + content[style_match.end():]

# 2. Extract script block (the large one at the bottom, there might be multiple, we want the last big one)
script_blocks = list(re.finditer(r'<script>(.*?)</script>', content, re.DOTALL | re.IGNORECASE))
if script_blocks:
    last_script = script_blocks[-1]
    js_content = last_script.group(1).strip()
    
    # We need to replace Jinja variables in JS
    js_content = js_content.replace("{{ session['username']|default ('guest') | tojson }}", "window.APP_CONFIG.currentUser")
    js_content = js_content.replace("{{ url_for('main.activate_account', id=999999) }}", "window.APP_CONFIG.urls.activateAccount")
    js_content = js_content.replace("{{ csrf_token() }}", "window.APP_CONFIG.csrfToken")
    
    with open(r'c:\Users\alcoh\PycharmProjects\boletim_sigaa\app\static\dashboard.js', 'w', encoding='utf-8') as f:
        f.write(js_content)
        
    config_script = '''<script>
    window.APP_CONFIG = {
        csrfToken: "{{ csrf_token() }}",
        currentUser: {{ session['username']|default('guest')|tojson }},
        urls: {
            activateAccount: "{{ url_for('main.activate_account', id=999999) }}"
        }
    };
    </script>
    <script src="{{ url_for('static', filename='dashboard.js') }}"></script>'''

    content = content[:last_script.start()] + config_script + content[last_script.end():]

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Extraction complete!')
