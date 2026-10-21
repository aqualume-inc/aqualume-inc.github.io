import json, math, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

query = '[out:json][timeout:90];area["ISO3166-2"="AT-7"]->.tirol;(nwr["amenity"="drinking_water"](area.tirol);nwr["drinking_water"~"^(yes|designated)$"](area.tirol);nwr["drinking_water:refill"="yes"](area.tirol););out center tags;'
endpoints = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
spots = None
errors = []
for endpoint in endpoints:
    try:
        req = Request(endpoint, data=urlencode({'data': query}).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Aqualume-Tirol-Snapshot/1.2 (https://aqualume-inc.github.io/)'})
        with urlopen(req, timeout=125) as response:
            payload = json.load(response)
        if payload.get('remark'):
            raise ValueError(payload['remark'])
        if not isinstance(payload.get('elements'), list):
            raise ValueError('Missing elements')
        unique = {}
        for item in payload['elements']:
            lat = item.get('lat', item.get('center', {}).get('lat'))
            lon = item.get('lon', item.get('center', {}).get('lon'))
            tags = item.get('tags', {})
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not math.isfinite(lat) or not math.isfinite(lon):
                continue
            if not (46 <= lat <= 49 and 9 <= lon <= 14):
                continue
            if tags.get('drinking_water') == 'no' or tags.get('access') in ('private', 'no'):
                continue
            key = str(item['type']) + '/' + str(item['id'])
            unique[key] = {'id': item['id'], 'type': item['type'], 'lat': lat, 'lon': lon, 'tags': tags}
        if len(unique) < 10:
            raise ValueError('Suspiciously empty result: refusing to replace snapshot')
        spots = sorted(unique.values(), key=lambda p: (p['type'], p['id']))
        break
    except Exception as exc:
        errors.append(endpoint + ': ' + str(exc))
        time.sleep(3)
if spots is None:
    raise SystemExit('Snapshot refresh failed; existing files preserved. ' + '; '.join(errors))

html_path = Path('index.html')
html = html_path.read_text()
replacement = '''async function load(){
 if(!map)return;const id=++serial;if(controller)controller.abort();controller=new AbortController();
 say('Tiroler Wasserstellen werden geladen …');
 let snapshot;
 try{snapshot=await request('./data/tirol-water.json',{signal:controller.signal},15000);if(!Array.isArray(snapshot.spots)||!snapshot.spots.length)throw Error('Leere Datendatei');cacheWrite('aqualume-snapshot',snapshot)}
 catch(e){if(id!==serial)return;snapshot=cacheRead('aqualume-snapshot');if(!snapshot){say('Datendatei noch nicht verfügbar. GitHub-Datenlauf prüfen oder gespeicherte Orte öffnen.');return}}
 if(id!==serial)return;const b=map.getBounds();spots=snapshot.spots.filter(p=>b.contains([p.lat,p.lon]));draw();
 const date=new Date(snapshot.generated_at).toLocaleString('de-AT');
 say(spots.length+' Wasserstellen in dieser Ansicht · '+snapshot.spots.length+' in Tirol · OSM-Datenabruf '+date+' · Keine aktuelle Qualitätsprüfung');
}
function update'''
html, count = re.subn(r'async function load\(\)\{.*?\nfunction update', lambda _: replacement, html, count=1, flags=re.S)
if count != 1:
    raise SystemExit('Unexpected application format; no files changed')
html = html.replace('Aqualume 1.1', 'Aqualume 1.2')
html = html.replace("L.map('map').setView", "L.map('map',{zoomControl:false}).setView")
zoom = '''const zoomButtons=L.Control.extend({options:{position:'topleft'},onAdd:function(){const box=L.DomUtil.create('div','leaflet-bar');for(const pair of [[1,'+','Karte vergrößern'],[-1,'−','Karte verkleinern']]){const btn=document.createElement('button');btn.type='button';btn.textContent=pair[1];btn.setAttribute('aria-label',pair[2]);btn.style.cssText='display:block;width:36px;height:36px;min-height:36px;padding:0;border-radius:0;background:white;color:black;font-size:24px';btn.onclick=()=>map.setZoom(map.getZoom()+pair[0]);box.append(btn)}L.DomEvent.disableClickPropagation(box);return box}});map.addControl(new zoomButtons());'''
if 'const zoomButtons=' not in html:
    html = html.replace('layer=L.layerGroup().addTo(map);', zoom + 'layer=L.layerGroup().addTo(map);')

worker = '''const CACHE='aqualume-static-v3';
const ASSETS=['./','./index.html','./manifest.webmanifest','./icon.svg','./data/tirol-water.json'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('aqualume-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;const u=new URL(e.request.url),local=u.origin===self.location.origin,lib=u.origin==='https://unpkg.com'&&u.pathname.startsWith('/leaflet@1.9.4/');if(!local&&!lib)return;const onlineFirst=local&&(e.request.mode==='navigate'||u.pathname.endsWith('.html')||u.pathname.endsWith('.json'));e.respondWith((async()=>{const cache=await caches.open(CACHE);if(onlineFirst){try{const r=await fetch(e.request,{cache:'no-cache'});if(!r.ok)throw Error('HTTP '+r.status);await cache.put(e.request,r.clone());return r}catch{const saved=await cache.match(e.request)||(e.request.mode==='navigate'?await cache.match('./index.html'):null);return saved||Response.error()}}const saved=await cache.match(e.request);if(saved)return saved;const r=await fetch(e.request);if(r.ok)await cache.put(e.request,r.clone());return r})())});
'''
output = {'generated_at': datetime.now(timezone.utc).isoformat(), 'source': 'OpenStreetMap contributors', 'license': 'ODbL-1.0', 'source_url': 'https://www.openstreetmap.org/copyright', 'coverage': 'Tirol, Austria (OSM area AT-7)', 'quality_note': 'Map records, not current water-quality certification. Access may be unknown.', 'spots': spots}
Path('data').mkdir(exist_ok=True)
Path('data/tirol-water.json').write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')))
html_path.write_text(html)
Path('sw.js').write_text(worker)
print('Prepared', len(spots), 'OSM water points; app and worker patched. Local format checks are not on-site verification.')
