"""Reutiliza o visual e os controles do painel desktop na versão Android."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
TRACKER = ROOT.parent / 'AnyPS5-Tracker'
template = (TRACKER / 'painel-template.html').read_text(encoding='utf-8')
assets = ROOT / 'build' / 'assets'
assets.mkdir(parents=True, exist_ok=True)
css = re.search(r'<style>([\s\S]*?)</style>', template)[1]
controls = re.search(r'<script>([\s\S]*?)</script>', template)[1]
body = re.search(r'<body>([\s\S]*?)<script>', template)[1]
body = body.replace(' target="_blank"', '')
body = body.replace('Seu histórico fica neste PC.', 'Seu histórico fica neste celular.')
body = body.replace('A escolha é salva neste navegador.', 'A escolha é salva neste celular.')
body = body.replace('Novos dados continuam sendo coletados a cada 5 minutos.', 'Novos dados são consultados ao abrir o app e no intervalo escolhido, enquanto ele está aberto.')
body = re.sub(r'<footer>[\s\S]*?</footer>', '<footer>AnyPS5 Tracker para Android · Atualiza ao abrir e enquanto o app está em uso. Escolha o intervalo em “Atualização do painel”.<br>Os últimos dados ficam disponíveis offline neste celular. Monitor independente, sem afiliação ao AnyPS5.</footer>', body)
body = body.replace('Painel local <span', 'Android <span')
body = body.replace('<h1>Cada avanço, em perspectiva.</h1>', '<h1>Cada avanço, em perspectiva.</h1><button type="button" class="top-link" onclick="location.reload()" style="background:transparent;margin:12px 0 2px">↻ Atualizar agora</button>')
(assets / 'panel.css').write_text(css, encoding='utf-8')
(assets / 'controls.js').write_text(controls, encoding='utf-8')
(assets / 'config.js').write_text('window.TrackerConfig = ' + json.dumps({'body': body}, ensure_ascii=False).replace('<', '\\u003c') + ';', encoding='utf-8')
(assets / 'mobile.js').write_text((ROOT / 'mobile.js').read_text(encoding='utf-8'), encoding='utf-8')
(assets / 'index.html').write_text('''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#101412"><title>AnyPS5 Tracker</title><link rel="stylesheet" href="panel.css"></head><body><main style="max-width:540px;margin:18vh auto;padding:24px"><div class="eyebrow">AnyPS5 Tracker · Android</div><h1>Consultando o progresso…</h1><p class="muted">Buscando os dados oficiais e seu histórico salvo.</p></main><script src="config.js"></script><script src="mobile.js"></script></body></html>''', encoding='utf-8')
print('Assets Android preparados a partir do painel atual.')
