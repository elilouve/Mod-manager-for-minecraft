MOD MANAGER - User guide
========================

A local program to organise Minecraft mods: database, online scan (Modrinth /
CurseForge), selection, download into a single zip, saved lists.
Everything runs on the local computer; no account is needed except an optional
free CurseForge API key.

1. Requirements
---------------
- Windows with Python 3.8 or newer (python.org, tick "Add Python to PATH"),.
- No other installation. Only the standard Python library is used.

2. Starting
-----------
Double-click lancer.bat. A console window opens and the browser shows the
interface (http://127.0.0.1:8765). Closing the console window stops the program.

Files created next to the program:
- mods.db        the database (mods, lists, categories)
- config.json    settings, including the CurseForge API key. NEVER share this file.
- telechargements/  default output folder (changeable in Settings)

Deleting mods.db and config.json resets the program to an empty state; they are
recreated at the next launch.

3. Settings
-----------
- CurseForge API key: free, created at console.curseforge.com (API keys).
  Modrinth does not need a key. Use "Test key" to check it.
- Output folder: where zip files are written (preferably not the system drive).
- Tracked Minecraft versions: versions shown in the table.
- Categories and tags: add, rename or delete categories, and assign an optional
  tag to each one (see section 7).
- Appearance: language (English / Francais), mode (automatic, light, dark) and
  theme colour (presets or custom). Changes are previewed immediately and
  applied with "Save".

4. Adding and importing mods
----------------------------
- "+ Add mod": enter a name and optionally a Modrinth and/or CurseForge link.
  "Fetch info from link" fills in name, icon, description, loaders and versions.
  Required dependencies found for the mod are linked automatically when already in the
  database. Missing ones are reported, with an offer to add them: each opens the Add mod
  window pre-filled, then the original form is restored with the dependency linked.
  An online check runs automatically when saving.
- "Search mods": searches Modrinth (and CurseForge with a key) by name through the official
  APIs and adds a result with one click. The usual online check then runs.
- "Import CSV": columns Mod/Name, Category, Loaders, Versions, Modrinth link,
  CurseForge link, Description, Notes (separator ";" or ","; French or English headers).
- "Export CSV": exports the table (or one list).

5. Online scan
--------------
"Scan online" searches each mod on Modrinth (and CurseForge when a key is set)
and fills in links, icon, description, loaders and versions.
Result per mod: Found / To check (uncertain match) / Not found.
When both sites know a mod, both links are stored. Unless unticked, the scan also reads
the required dependencies of every scanned mod: those already in the database are linked,
missing ones are listed for confirmation, then added (and themselves analysed for further dependencies) (with both links when available) and linked.
Options: only unscanned mods, retry unresolved mods, selection, or all mods.
The ↻ button on a row (or "Refresh" for a selection) re-checks mods after a link is
edited. If a mod stays "Not found", add its link manually (edit button).

Duplicates: after adding, editing, refreshing or scanning, entries that look like the same mod
(same Modrinth/CurseForge link or same name) are reported. Keep one: it is completed with the
other's data, links and lists, and the other is deleted. "Keep both" is remembered.
This check uses the local database only and adds no waiting time.

6. Downloading
--------------
Select mods, click "Download (zip)", choose the Minecraft version, loader and
source. Options:
- Try the other site when a mod is not found on the chosen one.
- Add required dependencies automatically. Dependencies are detected from
  Modrinth ("required") and CurseForge (relation "required"), added to the
  database under the category "Libraries & APIs" and included in the zip.
  When the option is unticked, the list is shown for confirmation instead.
- Add the category tag in front of file names (see below).
Mods that cannot be downloaded automatically (author restrictions, no
compatible version) are listed in a recap with direct links, also saved as
an HTML file next to the zip (..._MANUAL_DOWNLOAD.html).

7. Categories and tags
----------------------
Settings > Categories and tags (or "manage" in the left panel). A category can
be renamed (its mods follow) or deleted (its mods become uncategorised).
A tag is optional text such as "LIB" or "[W]". When "Add the category tag" is
ticked during a download, files become TAG_originalname.jar. If a tag ends with
a letter or digit, "_" is added; if it ends with a symbol (for example "]"), it is
used as written.

8. Lists
--------
Select mods, then "Lists > Save selection as a list" (new or existing list).
The "Lists" menu selects a list, exports all lists to a .json file and imports
lists from such a file. With a list opened in the left panel: rename, replace
its content with the current selection, export it as CSV or .json, or delete it.

9. Privacy
----------
The API key stays in config.json on the local computer and is only sent to
CurseForge. Do not share config.json or mods.db if they contain personal data.

10. Legal notes and disclaimer
------------------------------
- Not affiliated with, endorsed by or sponsored by Modrinth, CurseForge, Overwolf, Mojang
  or Microsoft. All names and trademarks belong to their owners.
- The program only calls the public Modrinth API and the official CurseForge API, at a
  limited rate, with an identifying User-Agent. It does not scrape web pages.
- Each user must use their OWN free CurseForge API key (never share a key) and is
  responsible for complying with the CurseForge and Modrinth terms of service
  (modrinth.com/legal/terms; CurseForge 3rd Party API terms). Modrinth's terms limit use
  of the service to personal, non-commercial purposes.
- Files are downloaded from the official sources only. Mods whose author disallows
  third-party distribution (no download URL from CurseForge) are never downloaded: they are
  listed with a link to the official page instead. Mod files stay under their authors'
  licenses; this program does not host or redistribute any mod.
- Information from the platforms (names, descriptions, icons) is stored locally for personal use.
  Do not publish mods.db.
- AI disclosure: this software was written with the assistance of an AI model (Claude, by
  Anthropic) and reviewed/tested by its human maintainer using mock servers and real use.
  It may contain bugs. Provided "as is" under the MIT License (see LICENSE), without warranty.
  Back up mods.db before updating.
