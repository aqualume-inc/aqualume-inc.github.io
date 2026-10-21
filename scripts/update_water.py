import json, math, os, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

FILE = Path('data/tirol-water.json')
STATUS = Path('data/update-status.json')
ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
QUERY = '[out:json][timeout:90];area["ISO3166-2"="AT-7"]->.tirol;(nwr["amenity"="drinking_water"](area.tirol);nwr["drinking_water"~"^(yes|designated)$"](area.tirol);nwr["drinking_water:refill"="yes"](area.tirol););out center tags;'

def normalize(payload):
    if payload.get('remark'):
        raise ValueError(str(payload['remark'])[:300])
    if not isinstance(payload.get('elements'), list):
        raise ValueError('Missing elements array')
    result = {}
    for item in payload['elements']:
        if not isinstance(item, dict) or item.get('type') not in ('node', 'way', 'relation') or not isinstance(item.get('id'), int):
            continue
        center = item.get('center') or {}
        lat, lon = item.get('lat', center.get('lat')), item.get('lon', center.get('lon'))
        tags = item.get('tags') or {}
        if not isinstance(tags, dict) or not all(type(v) in (int, float) and math.isfinite(v) for v in (lat, lon)):
            continue
        if not (46 <= lat <= 49 and 9 <= lon <= 14) or tags.get('drinking_water') == 'no' or tags.get('access') in ('private', 'no'):
            continue
        key = str(item['type']) + '/' + str(item['id'])
        result[key] = {'id': item['id'], 'type': item['type'], 'lat': lat, 'lon': lon, 'tags': tags}
    return sorted(result.values(), key=lambda p: (p['type'], p['id']))

def previous():
    try:
        data = json.loads(FILE.read_text())
        if not isinstance(data.get('generated_at'), str) or not isinstance(data.get('spots'), list):
            return None
        payload = {'elements': data['spots']}
        valid = normalize(payload)
        if len(valid) < 10 or len(valid) != len(data['spots']):
            return None
        return data
    except (OSError, ValueError, TypeError):
        return None

def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    temp.replace(path)

def main():
    old = previous()
    errors = []
    spots = None
    for attempt in range(2):
        for endpoint in ENDPOINTS:
            started = time.monotonic()
            print('Fetching', endpoint, 'attempt', attempt + 1, flush=True)
            try:
                req = Request(endpoint, data=urlencode({'data': QUERY}).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8', 'User-Agent': 'Aqualume-Water-Snapshot/1.3 (https://aqualume-inc.github.io/)'})
                with urlopen(req, timeout=120) as response:
                    candidate = normalize(json.load(response))
                minimum = max(10, int(len(old['spots']) * 0.6)) if old else 10
                if len(candidate) < minimum:
                    raise ValueError('Suspicious result: ' + str(len(candidate)) + ' records; minimum ' + str(minimum))
                spots = candidate
                print('Validated', len(spots), 'records in', round(time.monotonic() - started, 1), 'seconds', flush=True)
                break
            except Exception as exc:
                message = endpoint + ' attempt ' + str(attempt + 1) + ': ' + type(exc).__name__ + ': ' + str(exc)[:300]
                print(message, flush=True)
                errors.append(message)
                time.sleep(5)
        if spots is not None:
            break
        if attempt == 0:
            time.sleep(15)
    now = datetime.now(timezone.utc).isoformat()
    if spots is not None:
        data = {'generated_at': now, 'source': 'OpenStreetMap contributors', 'license': 'ODbL-1.0', 'source_url': 'https://www.openstreetmap.org/copyright', 'coverage': 'Tirol, Austria (OSM area AT-7)', 'quality_note': 'Map records, not current water-quality certification. Access may be unknown.', 'spots': spots}
        atomic_write(FILE, data)
        state = {'checked_at': now, 'refreshed': True, 'using_previous': False, 'data_generated_at': now, 'count': len(spots), 'errors': errors}
        heading = 'Water data refreshed'
    else:
        state = {'checked_at': now, 'refreshed': False, 'using_previous': bool(old), 'data_generated_at': old['generated_at'] if old else None, 'count': len(old['spots']) if old else 0, 'errors': errors}
        heading = 'Refresh failed; previous data preserved' if old else 'Refresh failed; no valid dataset available'
        print('::warning::' + heading, flush=True)
    atomic_write(STATUS, state)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write('## ' + heading + '\n\n' + 'Records: ' + str(state['count']) + '\n\nData timestamp: ' + str(state['data_generated_at']) + '\n\n' + '\n'.join('- ' + e for e in errors) + '\n')
    if spots is None and old is None:
        raise SystemExit('No valid snapshot; publication blocked. See data/update-status.json and job logs.')

if __name__ == '__main__':
    main()
