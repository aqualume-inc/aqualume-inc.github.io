import argparse, hashlib, json, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request

COUNTRIES = [('AT', 'Österreich', 'austria'), ('BE', 'Belgien', 'belgium'), ('BG', 'Bulgarien', 'bulgaria'), ('HR', 'Kroatien', 'croatia'), ('CY', 'Zypern', 'cyprus'), ('CZ', 'Tschechien', 'czech-republic'), ('DK', 'Dänemark', 'denmark'), ('EE', 'Estland', 'estonia'), ('FI', 'Finnland', 'finland'), ('FR', 'Frankreich', 'france'), ('DE', 'Deutschland', 'germany'), ('GR', 'Griechenland', 'greece'), ('HU', 'Ungarn', 'hungary'), ('IE', 'Irland', 'ireland-and-northern-ireland'), ('IT', 'Italien', 'italy'), ('LV', 'Lettland', 'latvia'), ('LT', 'Litauen', 'lithuania'), ('LU', 'Luxemburg', 'luxembourg'), ('MT', 'Malta', 'malta'), ('NL', 'Niederlande', 'netherlands'), ('PL', 'Polen', 'poland'), ('PT', 'Portugal', 'portugal'), ('RO', 'Rumänien', 'romania'), ('SK', 'Slowakei', 'slovakia'), ('SI', 'Slowenien', 'slovenia'), ('ES', 'Spanien', 'spain'), ('SE', 'Schweden', 'sweden')]
NOTE = 'Regional export extents, not exact EU legal borders. Ireland export includes Northern Ireland. Overseas territories and relations are not comprehensively covered. Missing map records are not proof that no water exists.'

def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    tmp.replace(path)

def index():
    rows = []
    for code, name, slug in COUNTRIES:
        row = {'code': code, 'name': name, 'extract': slug, 'status': 'pending'}
        path = Path('data/eu/' + code + '.json')
        if path.exists():
            data = json.loads(path.read_text())
            if data.get('spots'):
                row.update(status='ready', count=len(data['spots']), generated_at=data['generated_at'])
        rows.append(row)
    write('config/eu-countries.json', {'coverage_note': NOTE, 'countries': [{**r, 'status': 'pending'} for r in rows]})
    write('data/eu/index.json', {'coverage_note': NOTE, 'countries': rows})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--country', default='AT')
    args = parser.parse_args()
    code = COUNTRIES[datetime.now(timezone.utc).date().toordinal() % len(COUNTRIES)][0] if args.country == 'auto' else args.country.upper()
    selected = next((c for c in COUNTRIES if c[0] == code), None)
    if not selected:
        raise SystemExit('Unknown EU country code')
    index()
    import osmium
    source = 'https://download.geofabrik.de/europe/' + selected[2] + '-latest.osm.pbf'
    points = {}
    def acceptable(tags):
        return (tags.get('amenity') == 'drinking_water' or tags.get('drinking_water') in ('yes', 'designated') or tags.get('drinking_water:refill') == 'yes') and tags.get('drinking_water') != 'no' and tags.get('access') not in ('private', 'no')
    class Handler(osmium.SimpleHandler):
        def node(self, n):
            tags = dict(n.tags)
            if acceptable(tags) and n.location.valid():
                points['node/' + str(n.id)] = {'id': n.id, 'type': 'node', 'lat': n.location.lat, 'lon': n.location.lon, 'tags': tags, 'geometry_method': 'node'}
        def way(self, w):
            tags = dict(w.tags)
            if not acceptable(tags):
                return
            coords = [(n.location.lat, n.location.lon) for n in w.nodes if n.location.valid()]
            if coords and len(coords) == len(w.nodes):
                lat = (min(c[0] for c in coords) + max(c[0] for c in coords)) / 2
                lon = (min(c[1] for c in coords) + max(c[1] for c in coords)) / 2
                points['way/' + str(w.id)] = {'id': w.id, 'type': 'way', 'lat': lat, 'lon': lon, 'tags': tags, 'geometry_method': 'bbox_center_not_entrance'}
    with tempfile.TemporaryDirectory() as temp:
        raw, filtered = Path(temp) / 'region.pbf', Path(temp) / 'water.pbf'
        digest = hashlib.sha256()
        total, started = 0, time.monotonic()
        with urlopen(Request(source, headers={'User-Agent': 'Aqualume-EU-Importer/1.0 (https://aqualume-inc.github.io/)'}), timeout=120) as response, raw.open('wb') as dest:
            source_modified = response.headers.get('Last-Modified')
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > 7000000000 or time.monotonic() - started > 1800:
                    raise RuntimeError('Download exceeds runner safety limit')
                dest.write(block)
                digest.update(block)
        subprocess.run(['osmium', 'tags-filter', str(raw), 'nw/amenity=drinking_water', 'nw/drinking_water=yes,designated', 'nw/drinking_water:refill=yes', '-o', str(filtered)], check=True, timeout=1800)
        raw.unlink()
        Handler().apply_file(str(filtered), locations=True)
    if not points:
        raise RuntimeError('No water points: refusing to overwrite previous dataset')
    out = Path('data/eu/' + code + '.json')
    if out.exists():
        old = json.loads(out.read_text())
        if len(points) < len(old.get('spots', [])) * 0.6:
            raise RuntimeError('Suspicious count drop: keeping previous country file')
    write(out, {'country': code, 'generated_at': datetime.now(timezone.utc).isoformat(), 'source_url': source, 'source_modified': source_modified, 'source_sha256': digest.hexdigest(), 'source': 'OpenStreetMap contributors via Geofabrik', 'license': 'ODbL-1.0', 'coverage_note': NOTE, 'count': len(points), 'spots': list(points.values())})
    index()
    print('Imported', code, len(points), 'mapped water records; not current water-quality verification.')

if __name__ == '__main__':
    main()
