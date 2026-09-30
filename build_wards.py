"""Gán phường/xã (địa giới TP.HCM mới, 168 đơn vị) cho từng trạm bằng toạ độ.

Ranh giới: OpenStreetMap (Overpass API), relation TP.HCM = 1973756, admin_level=6.
Đầu ra: hcm_stations.js gồm HCM_STATIONS (GeoJSON điểm, có thuộc tính ward) và
HCM_WARDS (GeoJSON polygon đã đơn giản hoá + số trạm + bbox).
"""
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path

from shapely.geometry import Point, shape, mapping
from shapely.ops import linemerge, polygonize, unary_union
from shapely.geometry import LineString
from shapely.strtree import STRtree

ROOT = Path(__file__).parent
CACHE = ROOT / "hcm_wards_osm.json"
QUERY = ('[out:json][timeout:240];rel(1973756);map_to_area->.a;'
         'rel(area.a)["boundary"="administrative"]["admin_level"="6"];out geom;')
csv.field_size_limit(10**9)


def fetch():
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=urllib.parse.urlencode({"data": QUERY}).encode(),
        headers={"User-Agent": "charger-swap-map/1.0 (research)"})
    raw = urllib.request.urlopen(req, timeout=300).read()
    CACHE.write_bytes(raw)
    return json.loads(raw)


def ring_lines(members, role):
    return [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
            for m in members if m["type"] == "way" and m.get("role") == role and len(m.get("geometry", [])) > 1]


def build_geom(rel):
    outer = unary_union(list(polygonize(linemerge(ring_lines(rel["members"], "outer")))))
    inner_lines = ring_lines(rel["members"], "inner")
    if inner_lines:
        outer = outer.difference(unary_union(list(polygonize(linemerge(inner_lines)))))
    return outer.buffer(0)


def main():
    rels = fetch()["elements"]
    wards = []
    for r in rels:
        g = build_geom(r)
        if g.is_empty:
            print("bỏ qua (không dựng được):", r["tags"].get("name"))
            continue
        wards.append({"name": r["tags"]["name"], "geom": g})
    names = [w["name"] for w in wards]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        print("cảnh báo tên trùng:", dup)

    tree = STRtree([w["geom"] for w in wards])
    feats, counts, outside = [], {}, 0
    with open(ROOT / "battery_swap_stations_hcm.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            pt = Point(float(r["lng"]), float(r["lat"]))
            idx = [i for i in tree.query(pt) if wards[i]["geom"].covers(pt)]
            if idx:
                ward = wards[idx[0]]["name"]
            else:
                # ngoài mọi ranh giới: gán vào phường/xã gần nhất nếu cách < ~2 km, ngược lại để trống
                j = int(tree.nearest(pt))
                ward = wards[j]["name"] if wards[j]["geom"].distance(pt) < 0.02 else ""
                if not ward:
                    outside += 1
            counts[ward] = counts.get(ward, 0) + 1
            feats.append({"type": "Feature",
                          "geometry": {"type": "Point", "coordinates": [pt.x, pt.y]},
                          "properties": {"name": r["name"], "address": r["address"], "code": r["code"],
                                         "hotline": r["hotline"], "category": r["category_name"],
                                         "ward": ward, "hotline_xdv": r["hotline_xdv"],
                                         "direction": r["get_direction"]}})

    ward_feats = []
    for w in wards:
        g = w["geom"].simplify(0.0003, preserve_topology=True)
        minx, miny, maxx, maxy = w["geom"].bounds
        ward_feats.append({"type": "Feature", "geometry": mapping(g),
                           "properties": {"name": w["name"], "count": counts.get(w["name"], 0),
                                          "bbox": [round(minx, 5), round(miny, 5), round(maxx, 5), round(maxy, 5)]}})

    out = ("window.HCM_STATIONS=" + json.dumps({"type": "FeatureCollection", "features": feats},
                                                ensure_ascii=False, separators=(",", ":")) + ";\n"
           "window.HCM_WARDS=" + json.dumps({"type": "FeatureCollection", "features": ward_feats},
                                             ensure_ascii=False, separators=(",", ":")) + ";\n")
    (ROOT / "hcm_stations.js").write_text(out, encoding="utf-8")
    with_st = sum(1 for n in counts if n)
    print(f"{len(feats)} trạm, {len(wards)} phường/xã, {with_st} phường/xã có trạm, {outside} trạm ngoài ranh giới")


if __name__ == "__main__":
    main()
