import urllib.request, urllib.parse, re, sys, ssl
from http.cookiejar import CookieJar

ssl._create_default_https_context = ssl._create_unverified_context
cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
base = 'https://rximagenologiastgo.onrender.com'

def get(url):
    r = opener.open(urllib.request.Request(url))
    return r.read().decode('utf-8')

def post(url, data, referer):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={'Referer': referer})
    try:
        r = opener.open(req)
        return r.read().decode('utf-8'), r.getcode()
    except urllib.error.HTTPError as e:
        return e.read().decode('utf-8'), e.code

html = get(base + '/login/')
csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)
post(base + '/login/', {
    'csrfmiddlewaretoken': csrf, 'username': 'v1', 'password': 'Carlos1*', 'next': '/'
}, base + '/login/')

html = get(base + '/equipos/')
match = re.search(
    r'<h5 class="text-muted border-bottom pb-2"><i class="bi bi-question-circle"></i> Sin municipio asignado</h5>.*?<tbody>(.*?)</tbody>',
    html, re.DOTALL
)
if not match:
    print('No hay equipos sin municipio')
    sys.exit(0)

tbody = match.group(1)
ids = sorted(set(re.findall(r'/equipos/(\d+)/editar/', tbody)))
print(f'Equipos sin municipio: {len(ids)}')
for eid in ids:
    name_m = re.search(r'/equipos/' + eid + r'/editar/.*?<strong>(.*?)</strong>', tbody, re.DOTALL)
    name = name_m.group(1) if name_m else '?'
    print(f'  ID {eid}: {name}')

    edit_html = get(base + f'/equipos/{eid}/editar/')
    csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', edit_html).group(1)

    municipio_m = re.search(r'name="municipio" value="([^"]*)"', edit_html)
    current_mun = municipio_m.group(1) if municipio_m else ''
    if current_mun:
        print(f'    Ya tiene municipio: "{current_mun}", saltando')
        continue

    form_data = {'csrfmiddlewaretoken': csrf, 'municipio': 'Santiago de Cuba'}
    for m in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', edit_html):
        name = m.group(1)
        if name not in form_data:
            form_data[name] = m.group(2)
    for m in re.finditer(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', edit_html, re.DOTALL):
        form_data[m.group(1)] = m.group(2)
    for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>.*?<option[^>]*selected[^>]*value="([^"]*)"', edit_html, re.DOTALL):
        if m.group(1) not in form_data:
            form_data[m.group(1)] = m.group(2)

    body, code = post(base + f'/equipos/{eid}/editar/', form_data, base + f'/equipos/{eid}/editar/')
    print(f'    HTTP {code}')

print('Completado')
