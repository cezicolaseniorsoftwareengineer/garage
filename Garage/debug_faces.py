from PIL import Image

img = Image.open(r'c:\Users\LENOVO\OneDrive\Área de Trabalho\Garage_Game\Garage\app\static\img.png')
sw = 256

offsets = ['-16px -8px', '-119px -8px', '-222px -8px', '-325px -8px']
labels = ['s0 (Homem Branco)', 's1 (Homem Negro)', 's2 (Mulher Branca)', 's3 (Mulher Negra)']

html = """<html><body style="background:#222;color:#fff;font-family:monospace;padding:20px">
<h2>Sprite Sheet - 6 Personagens (topo de cada sprite)</h2>
<div style="display:flex;gap:20px">
"""
for i in range(6):
    html += f'<div style="text-align:center"><img src="/static/thumb_{i}.png" style="border:2px solid #fff;border-radius:8px;width:120px"><br>Sprite {i}</div>'
html += '</div>'
html += '<h2 style="margin-top:40px">Preview CSS Atual (circulos 72px com background-size 900% 280%)</h2>'
html += '<div style="display:flex;gap:30px">'
for i in range(4):
    html += f'''<div style="text-align:center">
        <div style="width:72px;height:72px;border-radius:50%;background:url(/static/img.png) no-repeat;background-size:900% 280%;background-position:{offsets[i]};border:2px solid gold;margin:0 auto"></div>
        <br>{labels[i]}
    </div>'''
html += '</div>'

# Show all 6 possible offsets
html += '<h2 style="margin-top:40px">Todos os 6 sprites como circulos (calculado)</h2>'
html += '<div style="display:flex;gap:30px">'
calc_offsets = [-18, -126, -234, -342, -450, -558]
for i in range(6):
    html += f'''<div style="text-align:center">
        <div style="width:72px;height:72px;border-radius:50%;background:url(/static/img.png) no-repeat;background-size:900% 280%;background-position:{calc_offsets[i]}px -8px;border:2px solid lime;margin:0 auto"></div>
        <br>Sprite {i} (offset {calc_offsets[i]}px)
    </div>'''
html += '</div></body></html>'

with open(r'c:\Users\LENOVO\OneDrive\Área de Trabalho\Garage_Game\Garage\app\static\debug_faces.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Debug page created: /static/debug_faces.html')
