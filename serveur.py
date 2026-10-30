#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minecraft Mod Manager  (MIT License, see LICENSE; developed with AI assistance, see README)
---------------------
Small local program: starts a mini web server on this computer (address 127.0.0.1,
reachable only from this machine) and opens the interface in the web browser.
No extra library is needed: only Python is required.
"""
import csv, difflib, hashlib, html, io, json, os, re, sqlite3, subprocess, sys
import threading, time, traceback, uuid, webbrowser, zipfile
import urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("GM_DB", os.path.join(BASE, "mods.db"))
CFG_PATH = os.environ.get("GM_CFG", os.path.join(BASE, "config.json"))
START_CSV = os.path.join(BASE, "mods_depart.csv")
MR = os.environ.get("MODRINTH_API", "https://api.modrinth.com/v2")
CF = os.environ.get("CURSEFORGE_API", "https://api.curseforge.com/v1")
THROTTLE = float(os.environ.get("GM_THROTTLE", "0.15"))
UA = "ModManager/1.0 (local open-source tool; personal use; not affiliated with Modrinth or CurseForge)"

LOADERS = ["forge", "neoforge", "fabric", "quilt"]
LABEL = {"forge": "Forge", "neoforge": "NeoForge", "fabric": "Fabric", "quilt": "Quilt"}
CF_LOADER = {1: "forge", 4: "fabric", 5: "quilt", 6: "neoforge"}
CF_LOADER_ID = {v: k for k, v in CF_LOADER.items()}
FIELDS = ["name", "category", "loaders", "versions", "modrinth_id", "modrinth_slug",
          "curseforge_id", "curseforge_slug", "icon_url", "description", "notes", "scan_status"]

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
DEFAULT_CFG = {"curseforge_key": "", "out_dir": os.path.join(BASE, "telechargements"),
               "tracked_versions": "1.20.1, 1.21.1, 1.21.11", "last_mc": "1.21.1",
               "last_loader": "neoforge", "last_source": "modrinth", "last_tags": False,
               "auto_deps": True, "lang": "en", "theme_mode": "auto", "theme_accent": "#2f7d46", "seeded": False}


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_cfg(upd):
    CF_STATE["blocked"] = False
    cfg = load_cfg()
    cfg.update({k: v for k, v in upd.items() if k in DEFAULT_CFG})
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


# ----------------------------------------------------------------------------
# Messages (English by default, French optional)
# ----------------------------------------------------------------------------
T = {
    "en": {
        "started": "Mod Manager started: %(url)s",
        "keep_open": "(keep this window open; closing it stops the program)",
        "initial_import": "Initial import: %(n)d mods added.",
        "no_port": "Unable to start: no free port available.",
        "denied": "Access denied (%(code)s) on %(url)s. Response: %(body)s",
        "http": "HTTP error %(code)s",
        "conn": "Connection failed (%(err)s)",
        "csv_col": "Column \"Mod\" not found in the file.",
        "bad_link": "Unrecognized link (expected: modrinth.com/mod/... or curseforge.com/minecraft/mc-mods/...).",
        "sc_deps_read": "Reading dependencies: %(name)s",
        "need_key": "A CurseForge API key is required first (Settings).",
        "no_mod_at_link": "No mod found at this address.",
        "list_dup": "A list with this name already exists.",
        "new_list": "New list",
        "unnamed": "Unnamed",
        "bad_path": "Path not allowed.",
        "unknown_action": "Unknown action.",
        "unknown_task": "Unknown task.",
        "host_refused": "Host refused",
        "req_refused": "Request refused",
        "not_found": "Not found",
        "error": "Error: %(e)s",
        "unexpected": "Unexpected error: %(e)s",
        "lists_file": "This file is not a list file from this program.",
        "searching": "Searching for files…",
        "search": "Searching: %(name)s",
        "downloading": "Downloading: %(name)s",
        "r_no_mr": "no Modrinth page known",
        "r_mr_404": "not found on Modrinth",
        "r_mr_ver": "no %(loader)s version for %(mc)s on Modrinth",
        "r_mr_file": "version without file on Modrinth",
        "r_cf_nokey": "CurseForge API key not set",
        "r_cf_nopage": "no CurseForge page known",
        "r_cf_404": "not found on CurseForge",
        "r_cf_ver": "no %(loader)s version for %(mc)s on CurseForge",
        "r_cf_blocked": "the author disallows downloads outside the CurseForge site",
        "r_dl": "download failed (%(err)s)",
        "r_hash": "corrupted file (checksum mismatch)",
        "r_unknown": "unknown",
        "rep_suffix": "_MANUAL_DOWNLOAD",
        "rep_title": "Mods to download manually",
        "rep_h1": "%(n)d mod(s) to download manually",
        "rep_intro": "Target: Minecraft %(mc)s, %(loader)s. Click \"Files\" to open the file list of the mod directly; tick the row when done.",
        "rep_mod": "Mod", "rep_why": "Reason", "rep_page": "Mod page", "rep_files": "Files %(mc)s",
        "rep_txt": "Mods to download manually - Minecraft %(mc)s, %(loader)s",
        "csv_headers": ["Mod", "Category", "Loaders", "Versions", "Modrinth link", "CurseForge link",
                        "Description", "Notes"],
        "dep_cat": "Libraries & APIs",
    },
    "fr": {
        "started": "Gestionnaire de mods démarré : %(url)s",
        "keep_open": "(laisser cette fenêtre ouverte ; la fermer arrête le programme)",
        "initial_import": "Import initial : %(n)d mods ajoutés.",
        "no_port": "Démarrage impossible : aucun port libre.",
        "denied": "Accès refusé (%(code)s) sur %(url)s. Réponse : %(body)s",
        "http": "Erreur HTTP %(code)s",
        "conn": "Connexion impossible (%(err)s)",
        "csv_col": "Colonne « Mod » introuvable dans le fichier.",
        "bad_link": "Lien non reconnu (attendu : modrinth.com/mod/... ou curseforge.com/minecraft/mc-mods/...).",
        "sc_deps_read": "Lecture des dépendances : %(name)s",
        "need_key": "Une clé d’API CurseForge est nécessaire au préalable (Paramètres).",
        "no_mod_at_link": "Aucun mod trouvé à cette adresse.",
        "list_dup": "Une liste porte déjà ce nom.",
        "new_list": "Nouvelle liste",
        "unnamed": "Sans nom",
        "bad_path": "Chemin non autorisé.",
        "unknown_action": "Action inconnue.",
        "unknown_task": "Tâche inconnue.",
        "host_refused": "Hôte refusé",
        "req_refused": "Requête refusée",
        "not_found": "Introuvable",
        "error": "Erreur : %(e)s",
        "unexpected": "Erreur inattendue : %(e)s",
        "lists_file": "Ce fichier n’est pas un fichier de listes de ce logiciel.",
        "searching": "Recherche des fichiers…",
        "search": "Recherche : %(name)s",
        "downloading": "Téléchargement : %(name)s",
        "r_no_mr": "aucune page Modrinth connue",
        "r_mr_404": "introuvable sur Modrinth",
        "r_mr_ver": "aucune version %(loader)s pour %(mc)s sur Modrinth",
        "r_mr_file": "version sans fichier sur Modrinth",
        "r_cf_nokey": "clé d’API CurseForge non renseignée",
        "r_cf_nopage": "aucune page CurseForge connue",
        "r_cf_404": "introuvable sur CurseForge",
        "r_cf_ver": "aucune version %(loader)s pour %(mc)s sur CurseForge",
        "r_cf_blocked": "l’auteur interdit le téléchargement hors du site CurseForge",
        "r_dl": "téléchargement impossible (%(err)s)",
        "r_hash": "fichier corrompu (somme de contrôle incorrecte)",
        "r_unknown": "inconnu",
        "rep_suffix": "_A_TELECHARGER_A_LA_MAIN",
        "rep_title": "Mods à télécharger manuellement",
        "rep_h1": "%(n)d mod(s) à télécharger manuellement",
        "rep_intro": "Cible : Minecraft %(mc)s, %(loader)s. Cliquer sur « Fichiers » pour ouvrir directement la liste des fichiers du mod ; cocher la ligne une fois terminé.",
        "rep_mod": "Mod", "rep_why": "Raison", "rep_page": "Page du mod", "rep_files": "Fichiers %(mc)s",
        "rep_txt": "Mods à télécharger manuellement - Minecraft %(mc)s, %(loader)s",
        "csv_headers": ["Mod", "Catégorie", "Loaders", "Versions", "Lien Modrinth", "Lien CurseForge",
                        "Description", "Notes"],
        "dep_cat": "Bibliothèques et API",
    },
}


def tr(key, **kw):
    lang = load_cfg().get("lang", "en")
    s = T.get(lang, T["en"]).get(key) or T["en"][key]
    return s % kw if kw and isinstance(s, str) else s


# ----------------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS mods(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT DEFAULT '',
  loaders TEXT DEFAULT '', versions TEXT DEFAULT '',
  modrinth_id TEXT, modrinth_slug TEXT, curseforge_id INTEGER, curseforge_slug TEXT,
  icon_url TEXT DEFAULT '', description TEXT DEFAULT '', notes TEXT DEFAULT '',
  scan_status TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS links(
  mod_id INTEGER NOT NULL REFERENCES mods(id) ON DELETE CASCADE,
  dep_id INTEGER NOT NULL REFERENCES mods(id) ON DELETE CASCADE,
  PRIMARY KEY(mod_id, dep_id));
CREATE TABLE IF NOT EXISTS lists(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS list_mods(
  list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
  mod_id INTEGER NOT NULL REFERENCES mods(id) ON DELETE CASCADE,
  PRIMARY KEY(list_id, mod_id));
CREATE TABLE IF NOT EXISTS categories(
  name TEXT PRIMARY KEY, tag TEXT DEFAULT '');
"""


def db():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    c = db()
    c.executescript(SCHEMA)
    # categories already used by mods become registered categories
    c.execute("INSERT OR IGNORE INTO categories(name) SELECT DISTINCT category FROM mods WHERE category<>''")
    c.commit()
    c.close()


def split(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def vkey(v):
    return tuple(int(x) for x in v.split("."))


def clean_versions(vs):
    return sorted({v for v in vs if re.fullmatch(r"\d+\.\d+(\.\d+)?", v)}, key=vkey)


def mod_dict(r):
    d = dict(r)
    d["loaders"] = split(d["loaders"])
    d["versions"] = split(d["versions"])
    d["mr_url"] = "https://modrinth.com/mod/%s" % d["modrinth_slug"] if d["modrinth_slug"] else ""
    d["cf_url"] = ("https://www.curseforge.com/minecraft/mc-mods/%s" % d["curseforge_slug"]
                   if d["curseforge_slug"] else "")
    return d


def get_mod(mid, c=None):
    own = c is None
    c = c or db()
    r = c.execute("SELECT * FROM mods WHERE id=?", (mid,)).fetchone()
    if own:
        c.close()
    return mod_dict(r) if r else None


def all_mods():
    c = db()
    mods = [mod_dict(r) for r in c.execute("SELECT * FROM mods ORDER BY lower(name)")]
    links = {}
    for r in c.execute("SELECT mod_id, dep_id FROM links"):
        links.setdefault(r[0], []).append(r[1])
    c.close()
    for m in mods:
        m["links"] = links.get(m["id"], [])
    return mods


def parse_url(u):
    """Recognizes a Modrinth or CurseForge link -> ('modrinth'|'curseforge', slug)."""
    u = (u or "").strip()
    m = re.search(r"modrinth\.com/(?:mod|plugin|datapack)/([\w\-.]+)", u)
    if m:
        return "modrinth", m.group(1)
    m = re.search(r"curseforge\.com/minecraft/mc-mods/([\w\-]+)", u)
    if m:
        return "curseforge", m.group(1)
    return None, None


def save_mod(data):
    """Creates or updates a mod. Returns its id."""
    c = db()
    f = {k: data[k] for k in FIELDS if k in data}
    for k in ("loaders", "versions"):
        if k in f and isinstance(f[k], list):
            f[k] = ",".join(f[k])
    for src, ukey, skey, ikey in (("modrinth", "modrinth_url", "modrinth_slug", "modrinth_id"),
                                  ("curseforge", "curseforge_url", "curseforge_slug", "curseforge_id")):
        if ukey in data:
            s, slug = parse_url(data[ukey])
            f[skey] = slug if s == src else None
            if not slug:
                f[ikey] = None
    mid = data.get("id")
    if mid:
        if f:
            sets = ", ".join("%s=?" % k for k in f)
            c.execute("UPDATE mods SET %s WHERE id=?" % sets, list(f.values()) + [mid])
    else:
        f.setdefault("name", tr("unnamed"))
        cols = ", ".join(f)
        cur = c.execute("INSERT INTO mods(%s) VALUES(%s)" % (cols, ",".join("?" * len(f))),
                        list(f.values()))
        mid = cur.lastrowid
    if f.get("category"):
        c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (f["category"],))
    if "links" in data:
        c.execute("DELETE FROM links WHERE mod_id=?", (mid,))
        for d in set(data["links"]):
            if d != mid:
                c.execute("INSERT OR IGNORE INTO links VALUES(?,?)", (mid, d))
    c.commit()
    c.close()
    return mid


def update_mod(mid, **f):
    c = db()
    sets = ", ".join("%s=?" % k for k in f)
    c.execute("UPDATE mods SET %s WHERE id=?" % sets, list(f.values()) + [mid])
    c.commit()
    c.close()


# ----------------------------------------------------------------------------
# Import / export CSV
# ----------------------------------------------------------------------------
def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def import_csv_text(text):
    text = text.lstrip("﻿")
    first = text.split("\n", 1)[0]
    delim = max(";,\t", key=first.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    if not rows:
        return {"added": 0, "skipped": 0}
    head = [h.strip().lower() for h in rows[0]]

    def col(*names):
        for n in names:
            if n in head:
                return head.index(n)
        return None

    i_name = col("mod", "nom", "name")
    i_cat = col("catégorie", "categorie", "category")
    i_load = col("loaders", "loader")
    i_ver = col("versions")
    i_desc = col("description")
    i_notes = col("notes")
    i_mr = col("lien modrinth", "modrinth link", "modrinth")
    i_cf = col("lien curseforge", "curseforge link", "curseforge")
    i_url = col("lien", "url", "link")
    i_vercols = [i for i, h in enumerate(head) if re.fullmatch(r"\d+\.\d+(\.\d+)?", h)]
    if i_name is None:
        raise ValueError(tr("csv_col"))
    c = db()
    existing = {norm(r[0]) for r in c.execute("SELECT name FROM mods")}
    added = skipped = 0
    for r in rows[1:]:
        if not r or len(r) <= i_name or not r[i_name].strip():
            continue
        name = r[i_name].strip()
        if norm(name) in existing:
            skipped += 1
            continue
        get = lambda i: r[i].strip() if i is not None and i < len(r) else ""
        loaders = [l for l in LOADERS if l in norm_loaders(get(i_load))]
        versions = set(split(get(i_ver).replace(";", ",")))
        for i in i_vercols:
            if i < len(r) and r[i].strip() not in ("", "—", "-"):
                versions.add(head[i])
        d = {"name": name, "category": get(i_cat), "loaders": loaders,
             "versions": clean_versions(versions), "description": get(i_desc), "notes": get(i_notes)}
        for u in (get(i_mr), get(i_cf), get(i_url)):
            s, slug = parse_url(u)
            if s == "modrinth":
                d["modrinth_slug"] = slug
            elif s == "curseforge":
                d["curseforge_slug"] = slug
        save_mod(d)
        existing.add(norm(name))
        added += 1
    c.close()
    return {"added": added, "skipped": skipped}


def norm_loaders(s):
    s = (s or "").lower()
    out = set()
    if "neoforge" in s:
        out.add("neoforge")
    if re.search(r"(?<!neo)forge", s):
        out.add("forge")
    for l in ("fabric", "quilt"):
        if l in s:
            out.add(l)
    return out


def export_csv_text(list_id=None):
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    w.writerow(tr("csv_headers"))
    keep = None
    if list_id:
        c = db()
        keep = {x[0] for x in c.execute("SELECT mod_id FROM list_mods WHERE list_id=?", (list_id,))}
        c.close()
    for m in all_mods():
        if keep is not None and m["id"] not in keep:
            continue
        w.writerow([m["name"], m["category"], ", ".join(LABEL[l] for l in m["loaders"] if l in LABEL),
                    ", ".join(m["versions"]), m["mr_url"], m["cf_url"], m["description"], m["notes"]])
    return "﻿" + out.getvalue()


# ----------------------------------------------------------------------------
# Modrinth and CurseForge APIs
# ----------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, msg, kind=None):
        super().__init__(msg)
        self.kind = kind  # "denied" | "conn" | None


_RATE = {"t": 0.0, "lock": threading.Lock()}


def rate_wait():
    """Keeps requests well under Modrinth's limit (300/min per IP): at most about 4 per second."""
    if THROTTLE <= 0:
        return
    with _RATE["lock"]:
        d = _RATE["t"] + 0.25 - time.time()
        if d > 0:
            time.sleep(d)
        _RATE["t"] = time.time()


def http_json(url, headers=None, tries=4):
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    last = None
    for i in range(tries):
        rate_wait()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (401, 403):
                try:
                    body = e.read().decode("utf-8", "replace")[:200].replace("\n", " ")
                except Exception:
                    body = ""
                raise ApiError(tr("denied", code=e.code, url=url.split("?")[0], body=body), kind="denied")
            if e.code in (429, 500, 502, 503, 504):
                try:
                    wait = float(e.headers.get("Retry-After") or 0)
                except ValueError:
                    wait = 0
                time.sleep(min(wait or 3 * (i + 1), 30))
                last = e
                continue
            raise ApiError(tr("http", code=e.code))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(2 * (i + 1))
    raise ApiError(tr("conn", err=last), kind="conn")


def q(s):
    return urllib.parse.quote(str(s), safe="")


def cf_headers():
    return {"x-api-key": load_cfg().get("curseforge_key", "").strip(), "User-Agent": UA}


def info_mr(p):
    return {"src": "modrinth", "id": p["id"], "slug": p["slug"], "title": p["title"],
            "description": p.get("description") or "", "icon": p.get("icon_url") or "",
            "loaders": [l for l in p.get("loaders", []) if l in LOADERS],
            "versions": clean_versions(p.get("game_versions", []))}


def info_cf(p):
    idx = p.get("latestFilesIndexes") or []
    logo = p.get("logo") or {}
    return {"src": "curseforge", "id": p["id"], "slug": p["slug"], "title": p["name"],
            "description": p.get("summary") or "",
            "icon": logo.get("thumbnailUrl") or logo.get("url") or "",
            "loaders": sorted({CF_LOADER[i["modLoader"]] for i in idx if i.get("modLoader") in CF_LOADER}),
            "versions": clean_versions({i["gameVersion"] for i in idx if i.get("gameVersion")})}


def mr_project(ref):
    p = http_json("%s/project/%s" % (MR, q(ref)))
    return info_mr(p) if p else None


def cf_mod(mod_id):
    d = http_json("%s/mods/%s" % (CF, mod_id), cf_headers())
    return info_cf(d["data"]) if d and d.get("data") else None


def cf_search(name=None, slug=None):
    params = {"gameId": 432, "classId": 6, "pageSize": 8}
    if slug:
        params["slug"] = slug
    else:
        params["searchFilter"] = name
    d = http_json("%s/mods/search?%s" % (CF, urllib.parse.urlencode(params)), cf_headers())
    return [info_cf(p) for p in (d or {}).get("data", [])]


def search_catalog(text):
    """Free-text search for the Add-from-search window: Modrinth, plus CurseForge when a key is set."""
    out = []
    facets = json.dumps([["project_type:mod"]])
    d = http_json("%s/search?query=%s&limit=12&facets=%s" % (MR, q(text), q(facets)))
    for h in (d or {}).get("hits", []):
        out.append({"src": "modrinth", "id": h["project_id"], "slug": h["slug"], "title": h["title"],
                    "description": h.get("description") or "", "icon": h.get("icon_url") or ""})
    if load_cfg().get("curseforge_key") and not CF_STATE["blocked"]:
        try:
            for i in cf_search(name=text)[:8]:
                out.append({k: i[k] for k in ("src", "id", "slug", "title", "description", "icon")})
        except ApiError as e:
            if e.kind != "denied":
                raise
            CF_STATE["blocked"] = True
    for o in out:
        dm = find_by_ref(o["src"], o["id"]) or find_by_slug(o["src"], o["slug"])
        o["in_db"] = dm["name"] if dm else None
    return out


def mr_search(name):
    facets = json.dumps([["project_type:mod"]])
    d = http_json("%s/search?query=%s&limit=8&facets=%s" % (MR, q(name), q(facets)))
    return [{"id": h["project_id"], "slug": h["slug"], "title": h["title"]}
            for h in (d or {}).get("hits", [])]


def score(name, title, slug):
    n = norm(name)
    best = 0.0
    for cand in (title, slug):
        c = norm(cand)
        if not c or not n:
            continue
        if n == c:
            return 1.0
        r = difflib.SequenceMatcher(None, n, c).ratio()
        if min(len(n), len(c)) >= 5 and (n in c or c in n):
            r = max(r, 0.8)
        best = max(best, r)
    return best


def best_match(name, cands, titlekey="title"):
    best, bs = None, 0.0
    for c in cands:
        s = score(name, c[titlekey], c["slug"])
        if s > bs:
            best, bs = c, s
    return best, bs


CF_STATE = {"blocked": False}


def search_best(src, names):
    """Best candidate on one site over several name variants: (info, score)."""
    best, bs = None, 0.0
    for nm in dict.fromkeys(n for n in names if n):
        if src == "modrinth":
            b, sc = best_match(nm, mr_search(nm))
        else:
            b, sc = best_match(nm, cf_search(name=nm), "title")
        if b and sc > bs:
            best, bs = b, sc
    if best and bs >= 0.6:
        return (mr_project(best["id"]) if src == "modrinth" else best), bs
    return None, bs


def name_variants(m, known):
    """Names to search for on the other site: the mod name plus the title/slug found on the first one."""
    out = [m["name"]]
    for i in known:
        out += [i["title"], i["slug"].replace("-", " ")]
    return out


def scan_curseforge(m, known=()):
    cf, s_cf = None, 0.0
    if m["curseforge_id"]:
        cf = cf_mod(m["curseforge_id"])
        s_cf = 1.0 if cf else 0.0
    elif m["curseforge_slug"]:
        res = cf_search(slug=m["curseforge_slug"])
        cf = res[0] if res else None
        s_cf = 1.0 if cf else 0.0
    else:
        cf, s_cf = search_best("curseforge", name_variants(m, known))
    return cf, s_cf


def scan_mod(mid, rename=True):
    """Searches the mod on Modrinth (and CurseForge if a key is set) and updates the database.
    Both links are kept when the mod exists on both sites."""
    m = get_mod(mid)
    if not m:
        return "absent"
    has_key = bool(load_cfg().get("curseforge_key")) and not CF_STATE["blocked"]
    mr = cf = None
    s_mr = s_cf = 0.0
    by_search = not (m["modrinth_id"] or m["modrinth_slug"] or m["curseforge_id"] or m["curseforge_slug"])
    has_mr_link = bool(m["modrinth_id"] or m["modrinth_slug"])
    has_cf_link = bool(m["curseforge_id"] or m["curseforge_slug"])
    if has_mr_link:
        mr = mr_project(m["modrinth_id"] or m["modrinth_slug"])
        s_mr = 1.0 if mr else 0.0
    if has_key and has_cf_link:
        try:
            cf, s_cf = scan_curseforge(m)
        except ApiError as e:
            if e.kind != "denied":
                raise
            CF_STATE["blocked"] = True
    if not has_mr_link:
        mr, s_mr = search_best("modrinth", name_variants(m, [cf] if cf else []))
    if has_key and not has_cf_link and not CF_STATE["blocked"]:
        try:
            cf, s_cf = scan_curseforge(m, [mr] if mr else [])
        except ApiError as e:
            if e.kind != "denied":
                raise
            CF_STATE["blocked"] = True  # key rejected: continue with Modrinth only
    if mr and cf and mr["slug"] == cf["slug"]:  # same slug on both sites: same mod
        s_mr = s_cf = max(s_mr, s_cf, 0.92)
    # a link found only by name similarity must not be added to an already certain source
    if mr and cf:
        if s_mr >= 0.92 and s_cf < 0.75:
            cf = None
        elif s_cf >= 0.92 and s_mr < 0.75:
            mr = None
    found = [i for i in (mr, cf) if i]
    if not found:
        update_mod(mid, scan_status="introuvable")
        return "introuvable"
    best = max(s_mr if mr else 0, s_cf if cf else 0)
    status = "ok" if best >= 0.92 else "à vérifier"
    upd = {"scan_status": status}
    if mr:
        upd.update(modrinth_id=mr["id"], modrinth_slug=mr["slug"])
    if cf:
        upd.update(curseforge_id=cf["id"], curseforge_slug=cf["slug"])
    loaders = [l for l in LOADERS if any(l in i["loaders"] for i in found)]
    versions = clean_versions({v for i in found for v in i["versions"]})
    if loaders:
        upd["loaders"] = ",".join(loaders)
    if versions:
        upd["versions"] = ",".join(versions)
    if not m["icon_url"]:
        upd["icon_url"] = next((i["icon"] for i in found if i["icon"]), "")
    if not m["description"]:
        upd["description"] = next((i["description"] for i in found if i["description"]), "")
    if status == "ok" and rename and by_search:  # a link given by the user never changes the chosen name
        upd["name"] = found[0]["title"]
    update_mod(mid, **upd)
    return status


def lookup_url(url):
    """For the add form: retrieves info from a Modrinth/CurseForge link."""
    src, slug = parse_url(url)
    if not src:
        raise ApiError(tr("bad_link"))
    if src == "modrinth":
        i = mr_project(slug)
    else:
        if not load_cfg().get("curseforge_key"):
            raise ApiError(tr("need_key"))
        res = cf_search(slug=slug)
        i = res[0] if res else None
    if not i:
        raise ApiError(tr("no_mod_at_link"))
    i["other"] = find_other(i)
    try:
        i["deps"] = lookup_deps(i)
    except ApiError:
        i["deps"] = []
    return i


def find_other(info):
    """The same mod on the other site (same slug, or a name match of at least 0.92), else None."""
    try:
        if info["src"] == "modrinth":
            if not load_cfg().get("curseforge_key") or CF_STATE["blocked"]:
                return None
            res = cf_search(slug=info["slug"])
            if res:
                return res[0]
            o, sc = search_best("curseforge", [info["title"], info["slug"].replace("-", " ")])
        else:
            o = mr_project(info["slug"])
            if o:
                return o
            o, sc = search_best("modrinth", [info["title"], info["slug"].replace("-", " ")])
        return o if o and sc >= 0.92 else None
    except ApiError:
        return None


DEP_CACHE = {}


def lookup_deps(info, with_other=True):
    """Required dependencies of a mod (for the add/edit form): newest file per loader, then
    each dependency is described and matched against the database."""
    refs = []
    if info["src"] == "modrinth":
        vs = http_json("%s/project/%s/version" % (MR, q(info["id"]))) or []
        vs.sort(key=lambda v: v["date_published"], reverse=True)
        seen = set()
        for v in vs:
            ls = [l for l in v.get("loaders", []) if l in LOADERS and l not in seen]
            if not ls:
                continue
            seen.update(ls)
            for d in v.get("dependencies", []):
                if d.get("dependency_type") != "required":
                    continue
                pid = d.get("project_id")
                if not pid and d.get("version_id"):
                    vv = http_json("%s/version/%s" % (MR, q(d["version_id"])))
                    pid = vv and vv.get("project_id")
                if pid and ("modrinth", pid) not in refs:
                    refs.append(("modrinth", pid))
            if len(seen) >= len(LOADERS):
                break
    else:
        d = http_json("%s/mods/%s/files?pageSize=30" % (CF, info["id"]), cf_headers()) or {}
        fs = sorted(d.get("data", []), key=lambda f: f["fileDate"], reverse=True)[:10]
        for f in fs:
            for x in f.get("dependencies", []):
                if x.get("relationType") == 3 and ("curseforge", x["modId"]) not in refs:
                    refs.append(("curseforge", x["modId"]))
    out = []
    for src, ref in refs[:12]:
        if src == "curseforge" and not load_cfg().get("curseforge_key"):
            continue
        key = (src, str(ref))
        if key not in DEP_CACHE:
            try:
                DEP_CACHE[key] = mr_project(ref) if src == "modrinth" else cf_mod(ref)
            except ApiError:
                DEP_CACHE[key] = None
        inf = DEP_CACHE[key]
        if not inf:
            continue
        inf = dict(inf)
        dm = find_by_ref(src, ref) or find_by_slug(src, inf["slug"])
        if not dm and with_other:
            inf["other"] = find_other(inf)
            o = inf["other"]
            dm = find_by_ref(o["src"], o["id"]) if o else None
            dm = dm or (find_by_slug(o["src"], o["slug"]) if o else None)
        inf["mod_id"] = dm["id"] if dm else None
        inf["db_name"] = dm["name"] if dm else None
        out.append(inf)
    return out


# ----------------------------------------------------------------------------
# Background tasks (scan, download)
# ----------------------------------------------------------------------------
JOBS = {}
ALLOWED_OPEN = set()


class Job:
    def __init__(self, kind):
        self.id = uuid.uuid4().hex[:8]
        self.kind = kind
        self.state = "running"  # running | need_deps | done | error | cancelled
        self.done = 0
        self.total = 0
        self.message = ""
        self.result = None
        self.cancel = False
        self.ask = None
        self.answer = None
        self.event = threading.Event()
        JOBS[self.id] = self

    def view(self):
        return {"id": self.id, "kind": self.kind, "state": self.state, "done": self.done,
                "total": self.total, "message": self.message, "result": self.result, "ask": self.ask}


def start_job(kind, fn, *args):
    job = Job(kind)

    def run():
        try:
            fn(job, *args)
            if job.state == "running":
                job.state = "cancelled" if job.cancel else "done"
        except ApiError as e:
            job.state, job.message = "error", str(e)
        except Exception as e:  # unexpected error: shown without crashing
            traceback.print_exc()
            job.state, job.message = "error", tr("unexpected", e=e)

    threading.Thread(target=run, daemon=True).start()
    return job


def add_link(mid, dep_id):
    if mid == dep_id:
        return False
    c = db()
    n = c.execute("INSERT OR IGNORE INTO links VALUES(?,?)", (mid, dep_id)).rowcount
    c.commit()
    c.close()
    return n > 0


def scan_worker(job, ids, rename=True, with_deps=True):
    job.total = len(ids)
    counts = {"ok": 0, "à vérifier": 0, "introuvable": 0, "erreur": 0}
    for n, mid in enumerate(ids):
        if job.cancel:
            break
        m = get_mod(mid)
        job.message = m["name"] if m else ""
        try:
            counts[scan_mod(mid, rename=rename)] += 1
        except ApiError as e:
            counts["erreur"] += 1
            job.last_error = str(e)
            if e.kind in ("conn", "denied"):
                job.state, job.message = "error", str(e)
                break
        job.done = n + 1
        time.sleep(THROTTLE)
    job.result = counts
    if CF_STATE["blocked"]:
        job.result["cf_refuse"] = True
    if with_deps and not job.cancel and job.state == "running":
        scan_dependencies(job, ids)


def scan_dependencies(job, ids):
    """Second phase of the scan: reads the required dependencies of every scanned mod, links the ones
    already in the database and offers to add the missing ones."""
    DEP_CACHE.clear()
    has_key = bool(load_cfg().get("curseforge_key")) and not CF_STATE["blocked"]
    job.total, job.done = len(ids), 0
    linked, pending = 0, {}
    for n, mid in enumerate(ids):
        if job.cancel:
            return
        job.done = n + 1
        m = get_mod(mid)
        if not m:
            continue
        job.message = tr("sc_deps_read", name=m["name"])
        if m["modrinth_id"]:
            info = {"src": "modrinth", "id": m["modrinth_id"]}
        elif m["curseforge_id"] and has_key:
            info = {"src": "curseforge", "id": m["curseforge_id"]}
        else:
            continue
        try:
            deps = lookup_deps(info, with_other=False)
        except ApiError as e:
            if e.kind in ("conn", "denied"):
                break
            continue
        for d in deps:
            if d["mod_id"]:
                linked += add_link(mid, d["mod_id"])
            else:
                c = pending.setdefault("%s:%s" % (d["src"], d["id"]), {"info": d, "by": []})
                c["by"].append(mid)
        time.sleep(THROTTLE)
    job.result["deps_linked"] = linked
    job.result["deps_added"] = []
    if not pending:
        return
    job.ask = {"deps": [{"key": k, "name": c["info"]["title"], "known": False,
                         "required_by": sorted({get_mod(i)["name"] for i in c["by"] if get_mod(i)})}
                        for k, c in pending.items()]}
    job.event.clear()
    job.state = "need_deps"
    job.event.wait()
    if job.cancel:
        return
    job.state, job.ask = "running", None
    accepted = set(job.answer or [])
    for k, c in pending.items():
        if k not in accepted:
            continue
        inf = c["info"]
        dm = find_by_ref(inf["src"], inf["id"]) or find_by_slug(inf["src"], inf["slug"])
        if not dm:
            d = {"name": inf["title"], "category": dep_category(), "scan_status": "ok", "loaders": inf["loaders"],
                 "versions": inf["versions"], "icon_url": inf["icon"], "description": inf["description"]}
            d.update({"modrinth_id": inf["id"], "modrinth_slug": inf["slug"]} if inf["src"] == "modrinth"
                     else {"curseforge_id": inf["id"], "curseforge_slug": inf["slug"]})
            did = save_mod(d)
            try:
                scan_mod(did, rename=False)
            except ApiError:
                pass
            dm = get_mod(did)
            job.result["deps_added"].append(dm["name"])
        for mid in c["by"]:
            linked += add_link(mid, dm["id"])
    job.result["deps_linked"] = linked


# ----------------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------------
def pages(m, src, mc, loader):
    if src == "modrinth" and m["modrinth_slug"]:
        base = "https://modrinth.com/mod/%s" % m["modrinth_slug"]
        return base, "%s/versions?g=%s&l=%s" % (base, mc, loader)
    if src == "curseforge" and m["curseforge_slug"]:
        base = "https://www.curseforge.com/minecraft/mc-mods/%s" % m["curseforge_slug"]
        return base, "%s/files/all?page=1&version=%s" % (base, mc)
    return None, None


def mod_pages(m, mc, loader, prefer):
    """Best links to finish by hand: chosen source, otherwise the other one, otherwise a search."""
    order = [prefer, "curseforge" if prefer == "modrinth" else "modrinth"]
    for s in order:
        p, f = pages(m, s, mc, loader)
        if p:
            return p, f
    n = q(m["name"])
    return ("https://modrinth.com/mods?q=%s" % n,
            "https://www.curseforge.com/minecraft/search?class=mc-mods&search=%s" % n)


RANK = {"release": 0, "beta": 1, "alpha": 2}


def resolve_modrinth(m, mc, loader):
    ref = m["modrinth_id"] or m["modrinth_slug"]
    if not ref:
        return None, tr("r_no_mr")
    vs = http_json("%s/project/%s/version?game_versions=%s&loaders=%s"
                   % (MR, q(ref), q(json.dumps([mc])), q(json.dumps([loader]))))
    if vs is None:
        return None, tr("r_mr_404")
    if not vs:
        return None, tr("r_mr_ver", loader=LABEL[loader], mc=mc)
    vs.sort(key=lambda v: v["date_published"], reverse=True)
    vs.sort(key=lambda v: RANK.get(v["version_type"], 3))
    v = vs[0]
    if not v["files"]:
        return None, tr("r_mr_file")
    f = next((x for x in v["files"] if x.get("primary")), v["files"][0])
    if not m["modrinth_id"]:
        update_mod(m["id"], modrinth_id=v["project_id"])
    deps = []
    for d in v.get("dependencies", []):
        if d.get("dependency_type") != "required":
            continue
        pid = d.get("project_id")
        if not pid and d.get("version_id"):
            vv = http_json("%s/version/%s" % (MR, q(d["version_id"])))
            pid = vv and vv.get("project_id")
        if pid:
            deps.append(("modrinth", pid))
    return {"source": "modrinth", "filename": f["filename"], "url": f["url"],
            "sha1": (f.get("hashes") or {}).get("sha1"), "version": v["version_number"],
            "deps": deps}, None


def resolve_curseforge(m, mc, loader):
    if not load_cfg().get("curseforge_key"):
        return None, tr("r_cf_nokey")
    cid = m["curseforge_id"]
    if not cid and m["curseforge_slug"]:
        res = cf_search(slug=m["curseforge_slug"])
        if res:
            cid = res[0]["id"]
            update_mod(m["id"], curseforge_id=cid)
    if not cid:
        return None, tr("r_cf_nopage")
    d = http_json("%s/mods/%s/files?gameVersion=%s&modLoaderType=%s&pageSize=50"
                  % (CF, cid, q(mc), CF_LOADER_ID[loader]), cf_headers())
    if d is None:
        return None, tr("r_cf_404")
    files = [f for f in d.get("data", []) if f.get("isAvailable", True)]
    if not files:
        return None, tr("r_cf_ver", loader=LABEL[loader], mc=mc)
    files.sort(key=lambda f: f["fileDate"], reverse=True)
    files.sort(key=lambda f: f.get("releaseType", 3))
    f = files[0]
    if not f.get("downloadUrl"):
        return None, tr("r_cf_blocked")
    sha1 = next((h["value"] for h in f.get("hashes", []) if h.get("algo") == 1), None)
    deps = [("curseforge", x["modId"]) for x in f.get("dependencies", []) if x.get("relationType") == 3]
    return {"source": "curseforge", "filename": f["fileName"], "url": f["downloadUrl"],
            "sha1": sha1, "version": f.get("displayName", ""), "deps": deps}, None


def resolve_mod(m, mc, loader, order):
    reasons = []
    for src in order:
        fn = resolve_modrinth if src == "modrinth" else resolve_curseforge
        res, why = fn(m, mc, loader)
        if res:
            return res, None
        reasons.append(why)
    return None, " ; ".join(dict.fromkeys(reasons))


def find_by_slug(src, slug):
    col = "modrinth_slug" if src == "modrinth" else "curseforge_slug"
    c = db()
    r = c.execute("SELECT * FROM mods WHERE %s=?" % col, (slug,)).fetchone()
    c.close()
    return mod_dict(r) if r else None


def dep_category():
    """Category used for dependencies added automatically: an existing library category, else a default."""
    c = db()
    r = c.execute("SELECT name FROM categories WHERE name IN (?, ?)",
                  (T["fr"]["dep_cat"], T["en"]["dep_cat"])).fetchone()
    c.close()
    return r[0] if r else tr("dep_cat")


def find_by_ref(src, ref):
    col = "modrinth_id" if src == "modrinth" else "curseforge_id"
    c = db()
    r = c.execute("SELECT * FROM mods WHERE %s=?" % col, (ref,)).fetchone()
    c.close()
    return mod_dict(r) if r else None


def download_bytes(url, tries=3):
    last = None
    for i in range(tries):
        try:
            h = {"User-Agent": UA}
            if "forgecdn.net" in url:  # since 16 July 2026 the CurseForge CDN requires the API key
                h.update(cf_headers())
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise ApiError(tr("r_dl", err=last))


def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|]+', "_", s).strip(" .")
    return s or "mods"


def download_worker(job, p):
    ids, mc, loader, source = p["ids"], p["mc"].strip(), p["loader"], p["source"]
    other = "curseforge" if source == "modrinth" else "modrinth"
    order = [source, other] if p.get("fallback", True) else [source]
    use_tags = bool(p.get("apply_tags"))
    cfg = save_cfg({"last_mc": mc, "last_loader": loader, "last_source": source,
                    "out_dir": p["out_dir"], "last_tags": use_tags,
                    "auto_deps": bool(p.get("auto_deps", True))})
    tagmap = {r["name"]: r["tag"] for r in categories_state()} if use_tags else {}
    n_tagged = 0
    out_dir = cfg["out_dir"]
    os.makedirs(out_dir, exist_ok=True)

    resolved = {}  # id du mod -> {"mod":..., "res":..., "why":...}
    declined = set()
    added_deps = []
    todo = list(dict.fromkeys(ids))
    job.message = tr("searching")
    while todo:
        job.total = len(resolved) + len(todo)
        newly = []
        for mid in todo:
            if job.cancel:
                return
            m = get_mod(mid)
            if not m:
                continue
            job.message = tr("search", name=m["name"])
            if not (m["modrinth_id"] or m["modrinth_slug"] or m["curseforge_id"] or m["curseforge_slug"]):
                try:
                    scan_mod(mid)
                    m = get_mod(mid)
                except ApiError:
                    pass
            try:
                res, why = resolve_mod(m, mc, loader, order)
            except ApiError as e:
                res, why = None, str(e)
            resolved[mid] = {"mod": m, "res": res, "why": why}
            newly.append(mid)
            job.done = len(resolved)
            time.sleep(THROTTLE)
        # required dependencies not yet in the selection
        cands = {}
        for mid in newly:
            e = resolved[mid]
            refs = []
            for src, ref in (e["res"] or {}).get("deps", []):
                dm = find_by_ref(src, ref)
                refs.append((dm, "%s:%s" % (src, ref), src, ref))
            for did in e["mod"].get("links", []) or links_of(mid):
                dm = get_mod(did)
                if dm:
                    refs.append((dm, "mod:%s" % dm["id"], None, None))
            for dm, key, src, ref in refs:
                if dm:
                    key = "mod:%s" % dm["id"]
                    if dm["id"] in resolved:
                        continue
                if key in declined:
                    continue
                cd = cands.setdefault(key, {"key": key, "mod_id": dm["id"] if dm else None,
                                            "name": dm["name"] if dm else None, "src": src,
                                            "ref": ref, "required_by": []})
                cd["required_by"].append(e["mod"]["name"])
        for cd in cands.values():
            if cd["name"] is None:
                try:
                    inf = mr_project(cd["ref"]) if cd["src"] == "modrinth" else cf_mod(cd["ref"])
                except ApiError:
                    inf = None
                cd["info"] = inf
                cd["name"] = inf["title"] if inf else "%s #%s" % (cd["src"], cd["ref"])
                # already in the database under another reference (same slug)? reuse it, avoid duplicates
                dm = find_by_slug(inf["src"], inf["slug"]) if inf else None
                if dm:
                    cd["mod_id"], cd["name"] = dm["id"], dm["name"]
                    update_mod(dm["id"], **{"modrinth_id" if inf["src"] == "modrinth" else "curseforge_id": inf["id"]})
                    if dm["id"] in resolved:
                        cd["skip"] = True
        cands = {k: v for k, v in cands.items() if not v.get("skip")}
        if not cands:
            break
        if p.get("auto_deps", True):
            accepted = set(cands)  # required dependencies are added without asking
        else:
            job.ask = {"deps": [{"key": c["key"], "name": c["name"], "known": c["mod_id"] is not None,
                                 "required_by": sorted(set(c["required_by"]))} for c in cands.values()]}
            job.event.clear()
            job.state = "need_deps"
            job.event.wait()
            if job.cancel:
                return
            job.state, job.ask = "running", None
            accepted = set(job.answer or [])
        todo = []
        for key, cd in cands.items():
            if key not in accepted:
                declined.add(key)
                continue
            mid = cd["mod_id"]
            if mid is None:
                inf = cd.get("info")
                d = {"name": cd["name"], "category": dep_category(), "scan_status": "ok"}
                if inf:
                    d.update(loaders=inf["loaders"], versions=inf["versions"], icon_url=inf["icon"],
                             description=inf["description"])
                    d.update({"modrinth_id": inf["id"], "modrinth_slug": inf["slug"]} if inf["src"] == "modrinth"
                             else {"curseforge_id": inf["id"], "curseforge_slug": inf["slug"]})
                mid = save_mod(d)
                try:
                    scan_mod(mid, rename=False)  # adds the link of the other site when it exists
                except ApiError:
                    pass
            added_deps.append(cd["name"])
            todo.append(mid)

    # --- download into the zip ---
    ok = [(mid, e) for mid, e in resolved.items() if e["res"]]
    fails = [(mid, e) for mid, e in resolved.items() if not e["res"]]
    base = safe_name(p.get("zip_name") or "mods")
    zip_base = "%s_%s_%s" % (base, mc, loader)
    zip_path = os.path.join(out_dir, zip_base + ".zip")
    n = 1
    while os.path.exists(zip_path):
        n += 1
        zip_path = os.path.join(out_dir, "%s_%d.zip" % (zip_base, n))
    job.total, job.done = len(ok), 0
    used = set()
    n_ok = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        for mid, e in ok:
            if job.cancel:
                break
            r = e["res"]
            job.message = tr("downloading", name=e["mod"]["name"])
            try:
                data = download_bytes(r["url"])
                if r["sha1"] and hashlib.sha1(data).hexdigest().lower() != r["sha1"].lower():
                    raise ApiError(tr("r_hash"))
                fname = r["filename"]
                pre = tag_prefix(tagmap.get(e["mod"]["category"] or "")) if use_tags else ""
                if pre:
                    fname = pre + fname
                if fname not in used:
                    zf.writestr(fname, data)
                    used.add(fname)
                    n_tagged += 1 if pre else 0
                n_ok += 1
            except ApiError as ex:
                e["res"], e["why"] = None, str(ex)
                fails.append((mid, e))
            job.done += 1
    if job.cancel:
        try:
            os.remove(zip_path)
        except OSError:
            pass
        return
    if not n_ok:
        try:
            os.remove(zip_path)
        except OSError:
            pass
        zip_path = None

    failures = []
    for mid, e in fails:
        page, files = mod_pages(e["mod"], mc, loader, source)
        failures.append({"name": e["mod"]["name"], "why": e["why"] or tr("r_unknown"), "page": page, "files": files})
    failures.sort(key=lambda f: f["name"].lower())
    rep_html = rep_txt = None
    if failures:
        rep_html = os.path.join(out_dir, zip_base + tr("rep_suffix") + ".html")
        rep_txt = os.path.join(out_dir, zip_base + tr("rep_suffix") + ".txt")
        write_reports(rep_html, rep_txt, failures, mc, loader)
        ALLOWED_OPEN.update([rep_html, rep_txt])
    ALLOWED_OPEN.update([out_dir] + ([zip_path] if zip_path else []))
    job.result = {"zip": zip_path, "out_dir": out_dir, "n_ok": n_ok, "failures": failures,
                  "report_html": rep_html, "report_txt": rep_txt, "added_deps": added_deps,
                  "n_tagged": n_tagged}


def links_of(mid):
    c = db()
    r = [x[0] for x in c.execute("SELECT dep_id FROM links WHERE mod_id=?", (mid,))]
    c.close()
    return r


def write_reports(path_html, path_txt, failures, mc, loader):
    e = html.escape
    lab = LABEL.get(loader, loader)
    rows = []
    for f in failures:
        rows.append(
            "<tr><td><label><input type=checkbox onchange=\"this.closest('tr').classList.toggle('done',this.checked)\"> "
            "<b>%s</b></label></td><td>%s</td><td><a href=\"%s\" target=_blank>%s</a></td>"
            "<td><a href=\"%s\" target=_blank>%s</a></td></tr>"
            % (e(f["name"]), e(f["why"]), e(f["page"]), e(tr("rep_page")), e(f["files"]), e(tr("rep_files", mc=mc))))
    page = """<!doctype html><html lang=%s><meta charset=utf-8>
<title>%s</title>
<style>body{font:15px system-ui,sans-serif;margin:2rem auto;max-width:980px;padding:0 1rem;color:#1d2420}
table{border-collapse:collapse;width:100%%}td,th{padding:.55rem .7rem;border-bottom:1px solid #d8ddd9;text-align:left;vertical-align:top}
tr.done{opacity:.4;text-decoration:line-through}a{color:#2b6c3f}h1{font-size:1.4rem}</style>
<h1>%s</h1>
<p>%s</p>
<table><tr><th>%s</th><th>%s</th><th></th><th></th></tr>%s</table></html>""" % (
        load_cfg().get("lang", "en"), e(tr("rep_title")), e(tr("rep_h1", n=len(failures))),
        e(tr("rep_intro", mc=mc, loader=lab)), e(tr("rep_mod")), e(tr("rep_why")), "".join(rows))
    with open(path_html, "w", encoding="utf-8") as fh:
        fh.write(page)
    lines = [tr("rep_txt", mc=mc, loader=lab), ""]
    for f in failures:
        lines += ["%s  (%s)" % (f["name"], f["why"]), "   %s" % f["files"], ""]
    with open(path_txt, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# ----------------------------------------------------------------------------
# Local web server
# ----------------------------------------------------------------------------
def api_state():
    c = db()
    lists = []
    for r in c.execute("SELECT id, name FROM lists ORDER BY lower(name)"):
        ids = [x[0] for x in c.execute("SELECT mod_id FROM list_mods WHERE list_id=?", (r["id"],))]
        lists.append({"id": r["id"], "name": r["name"], "ids": ids})
    c.close()
    cfg = load_cfg()
    cfg["has_key"] = bool(cfg.get("curseforge_key"))
    return {"mods": all_mods(), "lists": lists, "cfg": cfg, "categories": categories_state()}


def categories_state():
    c = db()
    rows = [{"name": r[0], "tag": r[1] or "", "count": r[2]} for r in c.execute(
        "SELECT c.name, c.tag, (SELECT COUNT(*) FROM mods m WHERE m.category=c.name) "
        "FROM categories c ORDER BY lower(c.name)")]
    c.close()
    return rows


def save_categories(d):
    """rows : [{old, name, tag}] (ajout si old vide, renommage si name != old), deleted : [noms]."""
    c = db()
    for name in d.get("deleted", []):
        c.execute("UPDATE mods SET category='' WHERE category=?", (name,))
        c.execute("DELETE FROM categories WHERE name=?", (name,))
    for r in d.get("rows", []):
        old, name, tag = (r.get("old") or "").strip(), (r.get("name") or "").strip(), r.get("tag") or ""
        if not name:
            continue
        if old and old != name:
            c.execute("UPDATE mods SET category=? WHERE category=?", (name, old))
            c.execute("DELETE FROM categories WHERE name=?", (old,))
        c.execute("INSERT INTO categories(name, tag) VALUES(?, ?) "
                  "ON CONFLICT(name) DO UPDATE SET tag=excluded.tag", (name, tag))
    c.commit()
    c.close()


def tag_prefix(tag):
    """File name prefix. If the tag ends with a letter/digit, an underscore is added as separator."""
    t = re.sub(r'[\\/:*?"<>|]+', "_", tag or "")
    if not t.strip():
        return ""
    return t + "_" if t[-1].isalnum() else t


def export_lists_text(list_id=None):
    mods = {m["id"]: m for m in all_mods()}
    c = db()
    out = []
    for r in c.execute("SELECT id, name FROM lists ORDER BY lower(name)"):
        if list_id and r["id"] != list_id:
            continue
        ids = [x[0] for x in c.execute("SELECT mod_id FROM list_mods WHERE list_id=?", (r["id"],))]
        ms = sorted((mods[i] for i in ids if i in mods), key=lambda m: m["name"].lower())
        out.append({"name": r["name"], "mods": [
            {"name": m["name"], "category": m["category"], "modrinth_slug": m["modrinth_slug"],
             "curseforge_slug": m["curseforge_slug"]} for m in ms]})
    c.close()
    return json.dumps({"format": "gestionnaire-mods-listes", "version": 1, "lists": out},
                      ensure_ascii=False, indent=1)


def import_lists_text(text):
    try:
        data = json.loads(text.lstrip("\ufeff"))
        assert isinstance(data, dict) and data.get("format") == "gestionnaire-mods-listes"
    except Exception:
        raise ApiError(tr("lists_file"))
    mods = all_mods()
    by_mr = {m["modrinth_slug"]: m["id"] for m in mods if m["modrinth_slug"]}
    by_cf = {m["curseforge_slug"]: m["id"] for m in mods if m["curseforge_slug"]}
    by_name = {norm(m["name"]): m["id"] for m in mods}
    n_lists = n_mods = created = 0
    for L in data.get("lists", []):
        name = (L.get("name") or "").strip()
        if not name:
            continue
        ids = []
        for e in L.get("mods", []):
            mr, cf, nm = e.get("modrinth_slug"), e.get("curseforge_slug"), e.get("name") or ""
            mid = (by_mr.get(mr) if mr else None) or (by_cf.get(cf) if cf else None) or by_name.get(norm(nm))
            if not mid:
                d = {"name": nm or "Sans nom", "category": e.get("category") or ""}
                if mr:
                    d["modrinth_slug"] = mr
                if cf:
                    d["curseforge_slug"] = cf
                mid = save_mod(d)
                created += 1
                by_name[norm(nm)] = mid
                if mr:
                    by_mr[mr] = mid
                if cf:
                    by_cf[cf] = mid
            ids.append(mid)
        c = db()
        r = c.execute("SELECT id FROM lists WHERE name=?", (name,)).fetchone()
        c.close()
        save_list({"id": r["id"] if r else None, "name": name, "ids": ids, "append": True})
        n_lists += 1
        n_mods += len(ids)
    return {"lists": n_lists, "mods": n_mods, "created": created}


def save_list(d):
    c = db()
    lid = d.get("id")
    name = (d.get("name") or "").strip() or tr("new_list")
    if lid:
        c.execute("UPDATE lists SET name=? WHERE id=?", (name, lid))
    else:
        try:
            lid = c.execute("INSERT INTO lists(name) VALUES(?)", (name,)).lastrowid
        except sqlite3.IntegrityError:
            raise ApiError(tr("list_dup"))
    if "ids" in d:
        if not d.get("append"):
            c.execute("DELETE FROM list_mods WHERE list_id=?", (lid,))
        for mid in d["ids"]:
            c.execute("INSERT OR IGNORE INTO list_mods VALUES(?,?)", (lid, mid))
    c.commit()
    c.close()
    return lid


def open_path(path):
    if path not in ALLOWED_OPEN or not os.path.exists(path):
        raise ApiError(tr("bad_path"))
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def host_ok(self):
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self.host_ok():
            return self.send(403, {"error": tr("host_refused")})
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                with open(os.path.join(BASE, "interface.html"), "rb") as f:
                    return self.send(200, f.read(), "text/html; charset=utf-8")
            if u.path == "/api/state":
                return self.send(200, api_state())
            if u.path == "/api/job":
                job = JOBS.get(urllib.parse.parse_qs(u.query).get("id", [""])[0])
                return self.send(200, job.view() if job else {"error": tr("unknown_task")})
            qs = urllib.parse.parse_qs(u.query)
            lid = int(qs["id"][0]) if qs.get("id") else None
            if u.path == "/api/export.csv":
                return self.send(200, export_csv_text(lid), "text/csv; charset=utf-8",
                                 {"Content-Disposition": 'attachment; filename="mes_mods.csv"'})
            if u.path == "/api/lists.json":
                return self.send(200, export_lists_text(lid), "application/json; charset=utf-8",
                                 {"Content-Disposition": 'attachment; filename="mes_listes.json"'})
            self.send(404, {"error": tr("not_found")})
        except Exception as e:
            traceback.print_exc()
            self.send(500, {"error": str(e)})

    def do_POST(self):
        if not self.host_ok() or "application/json" not in self.headers.get("Content-Type", ""):
            return self.send(403, {"error": tr("req_refused")})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            d = json.loads(self.rfile.read(n) or b"{}")
            self.send(200, self.route(urllib.parse.urlparse(self.path).path, d))
        except ApiError as e:
            self.send(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            self.send(500, {"error": tr("error", e=e)})

    def route(self, path, d):
        if path == "/api/mod":
            old = get_mod(d["id"]) if d.get("id") else None
            mid = save_mod(d)
            res = {"id": mid}
            new = get_mod(mid)
            changed = (not old or old["modrinth_slug"] != new["modrinth_slug"]
                       or old["curseforge_slug"] != new["curseforge_slug"]
                       or old["scan_status"] in ("", "introuvable", "à vérifier", None))
            if changed:  # live refresh of the mod info
                try:
                    res["scan"] = scan_mod(mid, rename=False)
                except ApiError as e:
                    res["scan_error"] = str(e)
            return res
        if path == "/api/mod/delete":
            c = db()
            c.executemany("DELETE FROM mods WHERE id=?", [(i,) for i in d["ids"]])
            c.commit()
            c.close()
            return {"ok": True}
        if path == "/api/mods/category":
            c = db()
            c.executemany("UPDATE mods SET category=? WHERE id=?", [(d["category"], i) for i in d["ids"]])
            if d["category"]:
                c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (d["category"],))
            c.commit()
            c.close()
            return {"ok": True}
        if path == "/api/categories/save":
            save_categories(d)
            return {"ok": True}
        if path == "/api/lists/import":
            return import_lists_text(d["text"])
        if path == "/api/lookup":
            return lookup_url(d.get("url"))
        if path == "/api/search":
            text = (d.get("q") or "").strip()
            return {"results": search_catalog(text) if len(text) >= 2 else []}
        if path == "/api/import":
            try:
                return import_csv_text(d["text"])
            except ValueError as e:
                raise ApiError(str(e))
        if path == "/api/list":
            return {"id": save_list(d)}
        if path == "/api/list/delete":
            c = db()
            c.execute("DELETE FROM lists WHERE id=?", (d["id"],))
            c.commit()
            c.close()
            return {"ok": True}
        if path == "/api/config":
            save_cfg({k: v for k, v in d.items() if k in (
                "curseforge_key", "out_dir", "tracked_versions", "lang", "theme_mode", "theme_accent")})
            return {"ok": True}
        if path == "/api/reset":
            c = db()
            for t_ in ("links", "list_mods", "lists", "mods", "categories"):
                c.execute("DELETE FROM %s" % t_)
            c.commit()
            c.close()
            save_cfg({"seeded": True})
            return {"ok": True}
        if path == "/api/config/test":
            r = http_json("%s/mods/search?gameId=432&classId=6&pageSize=1" % CF, cf_headers())
            return {"ok": bool(r and r.get("data"))}
        if path == "/api/scan":
            ids = d["ids"]
            if ids == "pending":
                c = db()
                ids = [r[0] for r in c.execute("SELECT id FROM mods WHERE scan_status='' OR scan_status IS NULL")]
                c.close()
            elif ids == "retry":
                c = db()
                ids = [r[0] for r in c.execute("SELECT id FROM mods WHERE scan_status IN ('introuvable','à vérifier')")]
                c.close()
            elif ids == "all":
                c = db()
                ids = [r[0] for r in c.execute("SELECT id FROM mods")]
                c.close()
            return start_job("scan", scan_worker, ids, d.get("rename", True), d.get("deps", True)).view()
        if path == "/api/download":
            return start_job("download", download_worker, d).view()
        if path == "/api/job/answer":
            job = JOBS[d["id"]]
            job.answer = d.get("accept", [])
            job.state, job.ask = "running", None  # avoids re-reading a stale request
            job.event.set()
            return {"ok": True}
        if path == "/api/job/cancel":
            job = JOBS[d["id"]]
            job.cancel = True
            job.event.set()
            return {"ok": True}
        if path == "/api/open":
            open_path(d["path"])
            return {"ok": True}
        raise ApiError(tr("unknown_action"))


def main():
    init_db()
    c = db()
    empty = c.execute("SELECT COUNT(*) FROM mods").fetchone()[0] == 0
    c.close()
    if empty and not load_cfg().get("seeded") and os.path.exists(START_CSV):
        with open(START_CSV, encoding="utf-8-sig") as f:
            r = import_csv_text(f.read())
        print(tr("initial_import", n=r["added"]))
    save_cfg({"seeded": True})
    port = 8765
    for a in sys.argv[1:]:
        if a.startswith("--port="):
            port = int(a.split("=")[1])
    srv = None
    for p in range(port, port + 15):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            port = p
            break
        except OSError:
            continue
    if not srv:
        print(tr("no_port"))
        return
    srv.daemon_threads = True
    url = "http://127.0.0.1:%d/" % port
    print("\n  " + tr("started", url=url))
    print("  " + tr("keep_open") + "\n")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
