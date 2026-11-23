# the autobiography of light

Deep-sky photographs placed where they sit in the cosmos (Cosmos tab), plus a searchable, filterable gallery (Gallery tab). Clicking a photo opens a large view with its details, wiki text and capture information.

Folder map:
- `index.html`: the whole website
- `catalog.json`: the list of photographs (this is the database)
- `photos/` and `photos/thumbs/`: the web-sized photos and thumbnails (made by the script)
- `data/`: star, constellation and Milky Way data
- `tools/`: the import script, a local preview server and the object catalog (run on your computer only)
- `import/`: your drop folder for new photos (never uploaded to the website or GitHub)
- `CNAME`: tells GitHub Pages to use cosmos.ckyr.us (only needed for GitHub hosting)

## 1. One-time setup

1. Install Python 3, then run `pip install requests pillow numpy`. (numpy is only needed for the orientation check described under "Rotation, mirrored photos and the star check"; everything else works without it.)
2. Get a free astrometry.net API key: sign in at https://nova.astrometry.net and open the API page of your account.
3. Give the script the key, either way:
   - Save it as the only line of a text file named `tools/api_key.txt` (ignored by git, so it never goes to GitHub), or
   - Set the environment variable `ASTROMETRY_API_KEY`. Mac or Linux: `export ASTROMETRY_API_KEY=your_key`. Windows PowerShell: `setx ASTROMETRY_API_KEY "your_key"`, then open a new terminal.

## 2. Add photographs

### The workflow
1. Copy your finished JPEG into the `import/` folder, for example `import/m31.jpg`.
2. Optional but recommended: create a details file with the same name, `import/m31.json`. Copy `import/_template.json` (every field, all empty) and rename it, or look at `import/_example_m31.json` for a filled-in example. You can also run `python3 tools/add_photo.py --template m31` to create an empty one. Files starting with an underscore are never imported.
3. Run `python3 tools/add_photo.py --all` (on Windows: `python`). The script solves every photo in `import/` and adds it to the site.
4. Finished photos and their JSON files are moved to `import/done/`. The script never changes or deletes your originals. Once you are happy, delete or archive `import/done/` yourself. The website only ever uses the resized copies in `photos/`.
5. Check the result locally (section 4), then publish (section 6 or 7).

The script saves a web copy (longest side 2400 px, never enlarged, no EXIF or GPS data) as `photos/<id>.jpg` and a 400 px thumbnail in `photos/thumbs/`, and adds an entry to `catalog.json`.

### The details file (JSON)
Open it in any text editor. Leave out or empty any field you don't need: empty fields are ignored. Keep the quotes and commas, and write a paragraph break in the story as `\n\n`.

```
{
  "title": "Andromeda Galaxy",
  "id": "m31",
  "designation": "M31",
  "date": "2025-10-12",
  "distance_ly": 2500000,
  "location": "Williamstown, Massachusetts",
  "telescope": "Your telescope",
  "exposure_seconds": 12000,
  "sub_exposure_seconds": 300,
  "frames": 40,
  "filters": ["L-eXtreme"],
  "story": "First paragraph.\n\nSecond paragraph."
}
```

| Field | Meaning |
|---|---|
| `title` | Name shown on the site. If missing, the designation or file name is used. |
| `id` | The photo's internal name. It is not shown on the website. It is used for the file names (`photos/<id>.jpg`), as the key in `catalog.json`, and by `--remove`. If you leave it empty it is made from the title ("Andromeda Galaxy" becomes `andromeda-galaxy`). Two photos with the same id are treated as the same photo: adding the second replaces the first. To keep several photos of one object, give each its own `id`. `_template.json` has an `id` line at the bottom; `_example_m31.json` does not, so add a line such as `"id": "m31",` yourself. See "Photo ids, editing and adding more photos of the same object" below. |
| `designation` | Catalog name such as M31, NGC 7000 or Caldwell 20. Shown under the thumbnail in the Cosmos tab and used to look up the object. |
| `date` | Capture date as YYYY-MM-DD. If empty, the photo's EXIF date is used (Lightroom exports include it unless you turned metadata off). |
| `hint` | An object name used to tell astrometry.net roughly where to look. Defaults to the designation. |
| `distance_ly` | Distance from Earth in light years (a plain number). Shown as "2.5 million light years". Used for the gallery's distance sort. |
| `location` | Capture location. |
| `telescope` | Telescope or lens (add the camera here too if you want it shown). Shown in the gallery and under Date in the details. |
| `exposure_seconds` | Total exposure in seconds. Shown as hours, minutes and seconds, for example 12000 becomes "3 h 20 min". If empty but `sub_exposure_seconds` and `frames` are given, it is calculated. |
| `sub_exposure_seconds`, `frames` | Length of each frame in seconds and the number of frames. Shown under "How it was captured". |
| `mosaic` | For example "2 x 2 panels", or true. Leave empty if it is a single frame. |
| `filters` | Text, or a list of filters. Shown under "How it was captured", below the number of frames. |
| `story` | The text under "Wiki" in the photo details (the field is still called `story`). You can write it yourself or adapt your own notes. Separate paragraphs with `\n\n`. See "Wiki text and credits" below. |
| `story_credit` | Optional small credit line shown under the wiki text, for example "Description adapted from Wikipedia (CC BY-SA 4.0)". |
| `object_type`, `messier`, `caldwell` | Normally filled in automatically (see below). Set them to override. |
| `constellation` | Optional text. |
| `ra`, `dec`, `width_deg`, `rotation` | Skip astrometry.net and use your own position. `ra` and `dec` are in decimal degrees (J2000), `width_deg` is the width of the image on the sky, and `rotation` is the angle astrometry.net reports for the picture: the page turns the photo clockwise by this many degrees from the north-up position. `ra`, `dec` and `width_deg` must all be given. |
| `flip` | `true` if the photo is a mirror image of the sky. It is normally set automatically (see "Rotation, mirrored photos and the star check"); set it by hand only if the check could not decide. |

Details also appear on the site automatically: the field of view (the arc on the sky) comes from the solve, and the position is shown in right ascension and declination.

### Command line options
Every field above can also be given on the command line, with `--` and dashes instead of underscores, for example `--id m31-wide --distance-ly 2500000 --exposure-seconds 12000 --location "My backyard"`. Command line values win over the JSON file.

| Command | What it does |
|---|---|
| `python3 tools/add_photo.py --all` | Adds every photo in `import/`. |
| `python3 tools/add_photo.py PHOTO.jpg --title "..." ...` | Adds one photo (reads `PHOTO.json` next to it if present). Does not move files. |
| `python3 tools/add_photo.py --template NAME` | Creates `import/NAME.json` with all fields. |
| `python3 tools/add_photo.py --list` | Lists the id and title of every photo in the catalog. |
| `python3 tools/add_photo.py --remove ID` | Removes a photo: its catalog entry, web copy and thumbnail. |
| `python3 tools/add_photo.py --remove-samples` | Removes all the sample photos. |
| `--max-size 2400` | Longest side of the web copy in pixels (default 2400). |
| `--push` | After the change, runs `git add -A`, `git commit` and `git push` (needs the setup in section 6). It does not pull first, so if GitHub rejects the push, follow Option 2 in "Publishing updates" (section 6). |

### Photo ids, editing and adding more photos of the same object
**What the id is.** Every photo has an `id`, its internal name. It is what the script uses to decide whether a photo is new or already exists. It comes from the `id` field of the JSON file (or `--id` on the command line). If that is empty, it is made from the **title**: lower case, with spaces and symbols turned into dashes, so the title "Andromeda Galaxy" gives `andromeda-galaxy`. It does not come from the file name (`m31.jpg` or `m31-wide.jpg` make no difference) and not from the designation. The id appears in the log when a photo is added (`Added 'Andromeda Galaxy' (id andromeda-galaxy)`), in `python3 tools/add_photo.py --list`, and as the `"id"` line of each entry in `catalog.json`.

**Rule: same id means same photo.** If you add a photo whose id already exists, the new one replaces the old one (image, thumbnail and all the details). The script does not warn you.

| You want to... | Do this |
|---|---|
| Add a photo of an object you have not photographed before | Import it as usual. The id is made from the title. |
| Add another photo of an object you already have, and keep both | The same title and designation are fine, but give the new photo its own `id`. |
| Fix a typo, or change the story, distance, location and so on of a photo that is already on the site | Edit `catalog.json` directly (below). |
| Replace the picture itself, for example with a better Lightroom export | Import again with the same `id` (below). |
| Delete a photo | `python3 tools/add_photo.py --remove ID` |

**Adding another photo of the same object.** Give each photo of the object a different id and keep the title as the object's name. For example:

`import/m31.json`:
```
{ "title": "Andromeda Galaxy", "designation": "M31", "id": "m31-2025-10", "date": "2025-10-12" }
```
`import/m31-wide.json`:
```
{ "title": "Andromeda Galaxy", "designation": "M31", "id": "m31-wide-2026", "date": "2026-09-20" }
```
Any short name made of letters, numbers and dashes works. A good habit is to give every photo an id from the start, such as the designation plus the year or a word that tells the photos apart. Both photos then appear in the gallery with the same title. On the sky, photos of the same object share one marker with a count until you zoom in, and clicking it lets you choose (see section 9). If you forget the id, the second photo silently replaces the first. Check with `--list` that you see both.

**Changing the text of a photo that is already on the site.** This is the easiest case, and it needs no new solve:
1. Open `catalog.json` in a text editor and find the photo, by searching for its title or its `"id"`.
2. Change the value you want, for example the text after `"story":`. Keep the quotes and commas, and write paragraph breaks as `\n\n`. Do not touch the automatic fields (`image`, `thumb`, `v`, `ra`, `dec`, `width_deg`, `height_deg`, `rotation`) unless you know what you are doing.
3. Save. If the site then shows nothing, a comma or quote is probably wrong. Run `python3 -m json.tool catalog.json > /dev/null` (on Windows: `python -m json.tool catalog.json > NUL`). It prints nothing if the file is fine, and an error with a line number if not.
4. Check it locally (section 4), then publish (section 6).

You can add a field that the photo does not have yet in the same way, with the same names as in the table above, for example `"location": "My backyard",` (and a comma after every line except the last one in the entry).

**Replacing the picture itself.** Import again with the same id:
1. Put the new JPEG in `import/`. For the JSON file, copy the old one back from `import/done/` (if you kept it) and edit it, or write a new one.
2. Set `"id"` to the id of the photo you are replacing. Use `--list` to look it up. If you never gave it an id, it is the title in lower case with dashes. If you also change the title, you must set the id explicitly, otherwise a new photo is created.
3. Include every field again. The entry is rebuilt from the JSON file, so anything you leave out (location, story, distance and so on) is lost, except what is filled in automatically.
4. Run `python3 tools/add_photo.py --all`. The old image and thumbnail are overwritten, and the photo is solved again.

### Rotation, mirrored photos and the star check
astrometry.net tests both a normal and a mirrored version of every photo, so it can solve a picture that is a mirror image of the sky (for example one flipped during editing). It reports the angle as a number that the page applies as a clockwise turn from the north-up position, and a "parity" value that says whether the picture is mirrored. The script now logs the parity, but the parity numbers are not documented clearly enough to rely on, so the script checks it another way: if numpy is installed, it compares the stars in your photo with a star catalogue (about 41,000 stars) and tests every rotation, with and without mirroring. The log then says one of three things:
- "orientation confirmed": the stars match the position and rotation, nothing changes.
- "this photo is a MIRROR IMAGE of the sky and will be shown flipped": the entry gets `"flip": true` and the page mirrors the photo so that it lines up.
- "not conclusive": the frame has too few bright catalogue stars (common for small fields), so nothing is changed. If you know a photo is mirrored, add `"flip": true` to its JSON file or its entry in `catalog.json`.

To check photos that are already in the catalog, run `python3 tools/check_orientation.py` (add `--fix` to mark mirrored photos, or `--id ID` for one photo). Use `--no-check` when adding a photo to skip the check.

If the page ever shows a photo turned the wrong way while the stars check says "ok", compare it with a wide-field picture of the same area, and send Claude the `rotation` value and what you see.

### Object type, Messier and Caldwell
astrometry.net only provides the position, so the script gets the object type and the Messier and Caldwell numbers from OpenNGC, a catalog included in `tools/catalog.json`. It looks for a name in the designation, hint or title (M, NGC, IC, Messier, Caldwell), and otherwise takes the catalog object closest to the centre of the image. The log shows what was matched; if it is wrong, set `object_type`, `messier` or `caldwell` in the JSON file. Things not in OpenNGC, such as Sharpless, Barnard or LDN objects, get no type automatically: set `object_type` yourself. The Gallery tab can then filter by type and by Messier or Caldwell, and sort by catalog number. Objects OpenNGC lists as clusters with nebulosity are labelled "Emission nebula".

Distance is not looked up automatically, so enter `distance_ly` yourself.

### If a solve fails
Add the object name as `hint`, or give `ra`, `dec` and `width_deg` yourself. Heavy star removal and very tight crops can make solving fail. If a photo looks mirrored or turned the wrong way in the Cosmos tab, see "Rotation, mirrored photos and the star check" below.

## 3. Remove photographs
Run `python3 tools/add_photo.py --list` to see the ids, then `python3 tools/add_photo.py --remove ID`. The site comes with ten sample photographs (ids starting with `sample-`) that show how every field looks. Remove them all in one go with:
```
python3 tools/add_photo.py --remove-samples
```
Removing only changes your local folder. Publish again for it to disappear from the website. To change the text of a photo, or to replace its picture, see "Photo ids, editing and adding more photos of the same object" in section 2.

## 4. View the site on your computer
In this folder run `python3 tools/serve.py` (on Windows: `python`), then open http://localhost:8000. Stop it with Ctrl+C. This server tells the browser not to cache anything, so you always see your latest changes. (Opening `index.html` directly does not work, because browsers block it from loading the data files, and the plain `python3 -m http.server` lets the browser keep old copies.)

## 5. Two ways to host it

| | GitHub Pages | Raspberry Pi |
|---|---|---|
| Cost | Free (public repository) | Free (you already own the Pi) |
| Uptime | Very high, no home equipment involved | Depends on your home power, internet and the Pi |
| Speed for visitors | Fast, GitHub's CDN | Fast if Cloudflare caches the photos, slower on the first visit |
| Size limits | About 1 GB site, 100 GB a month soft limit | Only your SD card or disk and your upload speed |
| Publishing | `git push` (the script's `--push` does it) | One `rsync` command |
| Setup effort | Low | Medium (web server, tunnel route) |
| Maintenance | None | You update the Pi and watch for problems |
| Privacy | The repository is public, including the tools folder | Only the website files are on the Pi |
| Rules | No online shops or commercial use | Cloudflare's terms discourage serving mostly large images and video through its free proxy; a small personal gallery is normally fine, but check their terms |

GitHub Pages is the simplest and most reliable. The Pi gives you full control and no limits. Only one of them can own cosmos.ckyr.us at a time. Either way, your computer's project folder is the master copy.

## 6. Option A: GitHub Pages

### First time
1. Create a new public repository on GitHub, for example `autobiography-of-light`. Do not add a README there.
2. In this folder run:
```
git init
git add -A
git commit -m "First version"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/autobiography-of-light.git
git push -u origin main
```
   GitHub asks you to sign in. Use a personal access token as the password, or use GitHub Desktop or `gh auth login`.
3. On GitHub: Settings, Pages, Build and deployment, Source "Deploy from a branch", Branch `main`, folder `/ (root)`, Save.
4. The site appears at https://YOUR-USERNAME.github.io/autobiography-of-light/ after a minute or two.

### Publishing updates
After adding, editing or removing photos, `catalog.json` and the files in `photos/` have changed. Publish with `--push` on the script, or by hand with one of the two options below.

**Option 1: regular update.** Use this when nothing has changed on GitHub's side:
```
git add -A
git commit -m "Add Andromeda"
git push
```

**Option 2: update after something changed on GitHub.** If the push fails with `! [rejected] main -> main (fetch first)` and "Updates were rejected because the remote contains work that you do not have locally", GitHub's copy of your branch has a commit that your computer does not have. This happens when something was committed on GitHub itself: changing or removing the custom domain in Settings, Pages (GitHub then adds or deletes the `CNAME` file by making a commit), editing a file in the browser, or pushing from another computer. Fix it by bringing those commits in first:
```
git add -A
git commit -m "Add Andromeda"
git pull --rebase
git push
```
If you already committed (for example because `--push` ran and then failed), skip the first two lines and run just `git pull --rebase` and `git push`. `git pull --rebase` downloads GitHub's commits and puts yours after them.

To see what GitHub has that you do not, run `git fetch` and then `git log HEAD..origin/main --stat`.

Notes for Option 2:
- If a text editor opens asking for a message, you ran plain `git pull` instead of `git pull --rebase`. Save and close it (in vim, type `:wq` and press Enter).
- If git reports a conflict, run `git status` to see the files. Open each one, look for the lines `<<<<<<<`, `=======` and `>>>>>>>`, keep the content you want (for `catalog.json`, keep the entries from both sides and make sure the commas are right), and delete those marker lines. Then run `git add FILE` and `git rebase --continue`. To cancel and return to where you were, run `git rebase --abort`.
- Never use `git push --force` to get around the error. It overwrites what is on GitHub.
- After pulling, check that the `CNAME` file still contains `cosmos.ckyr.us` and that the custom domain is still set in Settings, Pages. If you removed the domain in the settings, GitHub deleted the file: enter the domain again in the settings (GitHub creates the file again), run `git pull --rebase`, and then continue.
- Optional: run `git config pull.rebase true` once, so a plain `git pull` always works this way. Running `git pull --rebase` before every push is harmless: if nothing changed on GitHub it does nothing.

GitHub rebuilds the site by itself after each push, and the change is live in about a minute. There is no separate publish step. Refresh the page to see it. Deleted photos remain in git history, so the repository slowly grows.

### Use cosmos.ckyr.us (Cloudflare DNS)
1. Push the project with the `CNAME` file (already contains `cosmos.ckyr.us`).
2. On GitHub: repository Settings, Pages, Custom domain, enter `cosmos.ckyr.us`, Save. Changing or removing the custom domain later makes GitHub commit to your repository (it adds or deletes the `CNAME` file), so use Option 2 under "Publishing updates" for your next push.
3. In the Cloudflare dashboard, open the DNS records for ckyr.us and add: Type `CNAME`, Name `cosmos`, Target `YOUR-USERNAME.github.io` (without the repository name), Proxy status "DNS only" (grey cloud). If a record named `cosmos` already exists, delete it first.
4. Back in GitHub Pages settings, wait for the DNS check to succeed, then tick "Enforce HTTPS". The certificate can take up to an hour.
5. Optional: you can then turn Cloudflare's proxy (orange cloud) on if you want Cloudflare caching. If you do, set Cloudflare's SSL/TLS mode to "Full".
6. Optional: verify ckyr.us in your GitHub account settings (Settings, Pages, Add a domain) so nobody else can claim subdomains of it.

### Changing the web address later (for example from atlas.ckyr.us to cosmos.ckyr.us)
A GitHub Pages site has only one custom domain, so the old address stops working once you switch. Do the steps in this order:
1. On GitHub: repository Settings, Pages, Custom domain. Replace the old domain with the new one and Save. GitHub commits the new `CNAME` file. (The `CNAME` file holds just the domain on one line. You can also edit it yourself and push; the settings page and the file are two ways of changing the same thing.)
2. In Cloudflare, open the DNS records for ckyr.us and add: Type `CNAME`, Name `cosmos` (the new subdomain), Target `YOUR-USERNAME.github.io`, Proxy status "DNS only" (grey cloud).
3. Back in GitHub Pages settings, wait for "DNS check successful", then tick "Enforce HTTPS". A new certificate is issued for the new name, which can take up to an hour. Until then the new address may show a certificate warning.
4. Delete the old DNS record (`atlas`) in Cloudflare. Do not leave an unused subdomain pointing at GitHub Pages, because someone else could claim it.
5. On your computer run `git pull --rebase` to get GitHub's commit with the new `CNAME` file, then push your changes as usual (Option 2 under "Publishing updates").
6. Old links stop working. If you have shared the old address, a redirect rule in Cloudflare can forward it to the new one.
If you host on the Raspberry Pi instead, change the hostname of the route in your Cloudflare tunnel (section 7) and delete the old route.

## 7. Option B: Raspberry Pi

This assumes Raspberry Pi OS with SSH enabled, and `cloudflared` already running as a Cloudflare Tunnel connector.

### Set up the web server (once)
On the Pi:
```
sudo apt update && sudo apt install -y nginx rsync
sudo mkdir -p /var/www/atlas && sudo chown $USER /var/www/atlas
```
Create `/etc/nginx/sites-available/atlas` (for example with `sudo nano`) containing:
```
server {
    listen 8080;
    server_name _;
    root /var/www/atlas;
    index index.html;
    access_log off;                       # fewer writes to the SD card
    location /photos/ { add_header Cache-Control "public, max-age=604800"; }
    location /data/   { add_header Cache-Control "public, max-age=604800"; }
    location = /catalog.json { add_header Cache-Control "no-cache"; }
}
```
Then:
```
sudo ln -s /etc/nginx/sites-available/atlas /etc/nginx/sites-enabled/atlas
sudo nginx -t && sudo systemctl reload nginx
```

### Publish and update
From your computer, in the folder that contains the project folder (Mac or Linux; on Windows use WSL or WinSCP):
```
rsync -av --delete --exclude .git --exclude import --exclude tools --exclude README.md --exclude CNAME --exclude .gitignore atlas/ PI_USER@PI_ADDRESS:/var/www/atlas/
```
Use this same command for the first publish and for every update after you add or remove photos. It only copies what changed. Test on your home network at `http://PI_ADDRESS:8080`.

### Use cosmos.ckyr.us (Cloudflare Tunnel)
Because your domain and the tunnel are both on Cloudflare, no manual DNS record is needed.
1. In the Cloudflare dashboard go to Networking, Tunnels, and select your existing tunnel.
2. Under Routes choose Add route, then Published application.
3. Hostname: subdomain `cosmos`, domain `ckyr.us`. Service URL: `http://localhost:8080` (use `http://PI_ADDRESS:8080` if cloudflared runs on a different machine than nginx).
4. Save. Cloudflare creates the DNS record for you and serves the site over HTTPS.
If your tunnel is configured with a local `config.yml` instead, add an entry above the final catch-all rule, `- hostname: cosmos.ckyr.us` with `service: http://localhost:8080`, then run `cloudflared tunnel route dns YOUR-TUNNEL-NAME cosmos.ckyr.us` and restart cloudflared.

### Notes on the SD card
Serving a static site is mostly reading, which SD cards handle fine. Failures come mainly from heavy writing (logs, swap) and sudden power loss. The `access_log off` line above avoids most writes. A good-quality or high-endurance card, or a small SSD, and a clean shutdown help further. Keep your project folder on your computer as the master copy, so a dead card only means reinstalling and running the rsync command again.

## 8. Protecting the photographs
The site discourages casual saving: no right-click menu or dragging on photos, and the large view is a background image rather than a normal image. This cannot stop determined people, because any image a browser shows can be saved with developer tools or a screenshot. The practical protections are showing a smaller copy (use `--max-size 1600`), and adding a watermark (ask Claude to add this option). The website only ever contains the resized copies, never your originals.

## Using the site
**Cosmos tab.** Drag to look around, scroll or pinch to zoom, and click a photograph to open its details. The checkboxes at the bottom left switch Photos, Constellations, Names and Grid on and off (the grid starts switched on) (turn Photos off to read the constellation names behind them), and "Reset view" returns to the start. In the photo details, "Show on cosmos" flies to the photo's position.

**Gallery tab.** The search box at the top filters as you type: it looks at the title, designation, object type, location, telescope, filters, constellation, date, wiki text and distance, and understands catalog numbers such as `m31` or `caldwell 20`. It works together with the Catalog and Type filters and the Sort menu (including closest first by distance and by catalog number).

**Stars.** About 41,000 stars are included. Only the brightest are drawn when the whole cosmos is in view, and fainter ones appear as you zoom in, so the view stays clean. Drawing stops at the first star that is too faint, so the extra stars cost almost nothing.

**Byline.** The name in "photos by ..." links to the Instagram page https://www.instagram.com/the.autobiography.of.light/ (opens in a new tab), so visitors can get in touch there. To change the link, look for `instagram.com` in `index.html`.

## 9. In the Cosmos tab: many photos close together
Photos too small to show at true size appear as thumbnails. Neighbouring thumbnails merge into one marker with a count badge. Clicking it zooms in to separate different objects, or opens a list when the photos are of the same object. Zoomed in, photos are drawn at their real size and rotation, and clicking where several overlap opens the same list.

## Changing the Milky Way image
Two ready-made versions of `data/milkyway.jpg` exist: option A (4096x2048, about 0.7 MB) and option B (6144x3072, about 1.3 MB, more detail but about twice the memory in the browser, roughly 75 MB). To switch, copy the one you want into the `data` folder, name it exactly `milkyway.jpg` (replacing the old one), and push. To make visitors and your own browser pick up the new image immediately, also change `const V='6'` in `index.html` to a new value such as `'7'`. Test option B on your phone before publishing it: if the Milky Way background disappears there, go back to option A. When you stop moving, the page redraws the Milky Way at a higher quality, so it looks sharper at rest than while dragging.

## Wiki text and credits
Crediting a source does not give you permission to copy it. Text on websites such as Telescopius is normally protected by copyright, and I could not find their terms of use to check what reuse they allow. The safest approach is to use such pages as reference and write the wiki text in your own words, or to ask the site for permission. Facts such as distances and sizes are free to use; the wording is what is protected. If you do adapt text that comes with a licence that allows it (Wikipedia text is CC BY-SA 4.0, which requires credit and that your adaptation is shared under the same licence), put the credit in the `story_credit` field and it appears under the wiki text. There is no need to add anything to the site-wide credits for the wiki text.

## Updates and browser caching
Browsers keep copies of files, which is why a refresh was needed while you tested locally. Visitors to the finished site are much less affected: the catalog is always re-checked, every photo's address carries a version number that changes when you add or replace it, and the sky data carries a version in `index.html` (`const V`). Change that value if you ever replace `data/milkyway.jpg` or `data/sky.json`. GitHub Pages also tells browsers to keep files for only about ten minutes, so new photos normally show up within that time with a normal reload. If you later switch on Cloudflare's proxy, purge its cache from the Cloudflare dashboard after publishing changes to existing files.

## Data credits
- `data/sky.json` is derived from d3-celestial by Olaf Frohn (BSD-3-Clause, https://github.com/ofrohn/d3-celestial): about 41,000 stars down to magnitude 8, constellation lines and names. Fainter stars appear as you zoom in.
- `data/milkyway.jpg` is made from the Milky Way background of Deep Star Maps 2020 by NASA's Scientific Visualization Studio (https://svs.gsfc.nasa.gov/4851), tone-mapped, cleaned of faint-star grain and resized (4096x2048 or 6144x3072, see "Changing the Milky Way image") with RA 0h at the left edge.
- `tools/catalog.json` is derived from OpenNGC by Mattia Verga (CC-BY-SA 4.0, https://github.com/mattiaverga/OpenNGC): object types and Messier and Caldwell numbers.
