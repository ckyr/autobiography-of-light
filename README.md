# the autobiography of light

Deep-sky photographs placed where they sit in the sky (Sky tab), plus a filterable gallery (Gallery tab). Clicking a photo opens a large view with its details and story.

Folder map:
- `index.html`: the whole website
- `catalog.json`: the list of photographs (this is the database)
- `photos/` and `photos/thumbs/`: the web-sized photos and thumbnails (made by the script)
- `data/`: star, constellation and Milky Way data
- `tools/`: the import script, a local preview server and the object catalog (run on your computer only)
- `import/`: your drop folder for new photos (never uploaded to the website or GitHub)
- `CNAME`: tells GitHub Pages to use atlas.ckyr.us (only needed for GitHub hosting)

## 1. One-time setup

1. Install Python 3, then run `pip install requests pillow`.
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
| `id` | Optional unique id, used for the file names and for removing. Default: made from the title. Adding a photo with an existing id replaces it. Give a different title or `id` to keep two photos of the same object. |
| `designation` | Catalog name such as M31, NGC 7000 or Caldwell 20. Shown under the thumbnail on the sky and used to look up the object. |
| `date` | Capture date as YYYY-MM-DD. If empty, the photo's EXIF date is used (Lightroom exports include it unless you turned metadata off). |
| `hint` | An object name used to tell astrometry.net roughly where to look. Defaults to the designation. |
| `distance_ly` | Distance from Earth in light years (a plain number). Shown as "2.5 million light years". Used for the gallery's distance sort. |
| `location` | Capture location. |
| `telescope` | Telescope or lens (add the camera here too if you want it shown). Shown in the gallery and under Date in the details. |
| `exposure_seconds` | Total exposure in seconds. Shown as hours, minutes and seconds, for example 12000 becomes "3 h 20 min". If empty but `sub_exposure_seconds` and `frames` are given, it is calculated. |
| `sub_exposure_seconds`, `frames` | Length of each frame in seconds and the number of frames. Shown under "How it was made". |
| `mosaic` | For example "2 x 2 panels", or true. Leave empty if it is a single frame. |
| `filters` | Text, or a list of filters. |
| `story` | The description under "The story". You can write it yourself or adapt your own notes. Separate paragraphs with `\n\n`. See "Story text and credits" below. |
| `story_credit` | Optional small credit line shown under the story, for example "Description adapted from Wikipedia (CC BY-SA 4.0)". |
| `object_type`, `messier`, `caldwell` | Normally filled in automatically (see below). Set them to override. |
| `constellation` | Optional text. |
| `ra`, `dec`, `width_deg`, `rotation` | Skip astrometry.net and use your own position. `ra` and `dec` are in decimal degrees (J2000), `width_deg` is the width of the image on the sky, and `rotation` is the direction of the image's top edge in degrees east of north. `ra`, `dec` and `width_deg` must all be given. |

Details also appear on the site automatically: the field of view (the arc on the sky) comes from the solve, and the position is shown in right ascension and declination.

### Command line options
Every field above can also be given on the command line, with `--` and dashes instead of underscores, for example `--distance-ly 2500000 --exposure-seconds 12000 --location "My backyard"`. Command line values win over the JSON file.

| Command | What it does |
|---|---|
| `python3 tools/add_photo.py --all` | Adds every photo in `import/`. |
| `python3 tools/add_photo.py PHOTO.jpg --title "..." ...` | Adds one photo (reads `PHOTO.json` next to it if present). Does not move files. |
| `python3 tools/add_photo.py --template NAME` | Creates `import/NAME.json` with all fields. |
| `python3 tools/add_photo.py --list` | Lists the id and title of every photo in the catalog. |
| `python3 tools/add_photo.py --remove ID` | Removes a photo: its catalog entry, web copy and thumbnail. |
| `python3 tools/add_photo.py --remove-samples` | Removes all the sample photos. |
| `--max-size 2400` | Longest side of the web copy in pixels (default 2400). |
| `--push` | After the change, runs `git add -A`, `git commit` and `git push` (needs the setup in section 6). |

### Object type, Messier and Caldwell
astrometry.net only provides the position, so the script gets the object type and the Messier and Caldwell numbers from OpenNGC, a catalog included in `tools/catalog.json`. It looks for a name in the designation, hint or title (M, NGC, IC, Messier, Caldwell), and otherwise takes the catalog object closest to the centre of the image. The log shows what was matched; if it is wrong, set `object_type`, `messier` or `caldwell` in the JSON file. Things not in OpenNGC, such as Sharpless, Barnard or LDN objects, get no type automatically: set `object_type` yourself. The Gallery tab can then filter by type and by Messier or Caldwell, and sort by catalog number. Objects OpenNGC lists as clusters with nebulosity are labelled "Emission nebula".

Distance is not looked up automatically, so enter `distance_ly` yourself.

### If a solve fails
Add the object name as `hint`, or give `ra`, `dec` and `width_deg` yourself. Heavy star removal and very tight crops can make solving fail. If a photo appears mirrored on the sky, tell Claude and a flip option can be added.

## 3. Remove photographs
Run `python3 tools/add_photo.py --list` to see the ids, then `python3 tools/add_photo.py --remove ID`. The site comes with ten sample photographs (ids starting with `sample-`) that show how every field looks. Remove them all in one go with:
```
python3 tools/add_photo.py --remove-samples
```
Removing only changes your local folder. Publish again for it to disappear from the website. To change a title, story or distance, edit `catalog.json` directly or add the photo again with the same id.

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

GitHub Pages is the simplest and most reliable. The Pi gives you full control and no limits. Only one of them can own atlas.ckyr.us at a time. Either way, your computer's project folder is the master copy.

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
After adding or removing photos, `catalog.json` and the files in `photos/` have changed. Publish with `--push` on the script, or by hand:
```
git add -A
git commit -m "Add Andromeda"
git push
```
GitHub rebuilds the site by itself after each push, and the change is live in about a minute. There is no separate publish step. Refresh the page to see it. Deleted photos remain in git history, so the repository slowly grows.

### Use atlas.ckyr.us (Cloudflare DNS)
1. Push the project with the `CNAME` file (already contains `atlas.ckyr.us`).
2. On GitHub: repository Settings, Pages, Custom domain, enter `atlas.ckyr.us`, Save.
3. In the Cloudflare dashboard, open the DNS records for ckyr.us and add: Type `CNAME`, Name `atlas`, Target `YOUR-USERNAME.github.io` (without the repository name), Proxy status "DNS only" (grey cloud). If a record named `atlas` already exists, delete it first.
4. Back in GitHub Pages settings, wait for the DNS check to succeed, then tick "Enforce HTTPS". The certificate can take up to an hour.
5. Optional: you can then turn Cloudflare's proxy (orange cloud) on if you want Cloudflare caching. If you do, set Cloudflare's SSL/TLS mode to "Full".
6. Optional: verify ckyr.us in your GitHub account settings (Settings, Pages, Add a domain) so nobody else can claim subdomains of it.

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

### Use atlas.ckyr.us (Cloudflare Tunnel)
Because your domain and the tunnel are both on Cloudflare, no manual DNS record is needed.
1. In the Cloudflare dashboard go to Networking, Tunnels, and select your existing tunnel.
2. Under Routes choose Add route, then Published application.
3. Hostname: subdomain `atlas`, domain `ckyr.us`. Service URL: `http://localhost:8080` (use `http://PI_ADDRESS:8080` if cloudflared runs on a different machine than nginx).
4. Save. Cloudflare creates the DNS record for you and serves the site over HTTPS.
If your tunnel is configured with a local `config.yml` instead, add an entry above the final catch-all rule, `- hostname: atlas.ckyr.us` with `service: http://localhost:8080`, then run `cloudflared tunnel route dns YOUR-TUNNEL-NAME atlas.ckyr.us` and restart cloudflared.

### Notes on the SD card
Serving a static site is mostly reading, which SD cards handle fine. Failures come mainly from heavy writing (logs, swap) and sudden power loss. The `access_log off` line above avoids most writes. A good-quality or high-endurance card, or a small SSD, and a clean shutdown help further. Keep your project folder on your computer as the master copy, so a dead card only means reinstalling and running the rsync command again.

## 8. Protecting the photographs
The site discourages casual saving: no right-click menu or dragging on photos, and the large view is a background image rather than a normal image. This cannot stop determined people, because any image a browser shows can be saved with developer tools or a screenshot. The practical protections are showing a smaller copy (use `--max-size 1600`), and adding a watermark (ask Claude to add this option). The website only ever contains the resized copies, never your originals.

## 9. On the sky: many photos close together
Photos too small to show at true size appear as thumbnails. Neighbouring thumbnails merge into one marker with a count badge. Clicking it zooms in to separate different objects, or opens a list when the photos are of the same object. Zoomed in, photos are drawn at their real size and rotation, and clicking where several overlap opens the same list.

## Story text and credits
Crediting a source does not give you permission to copy it. Text on websites such as Telescopius is normally protected by copyright, and I could not find their terms of use to check what reuse they allow. The safest approach is to use such pages as reference and write the story in your own words, or to ask the site for permission. Facts such as distances and sizes are free to use; the wording is what is protected. If you do adapt text that comes with a licence that allows it (Wikipedia text is CC BY-SA 4.0, which requires credit and that your adaptation is shared under the same licence), put the credit in the `story_credit` field and it appears under the story. There is no need to add anything to the site-wide credits for story text.

## Updates and browser caching
Browsers keep copies of files, which is why a refresh was needed while you tested locally. Visitors to the finished site are much less affected: the catalog is always re-checked, every photo's address carries a version number that changes when you add or replace it, and the sky data carries a version in `index.html` (`const V`). Change that value if you ever replace `data/milkyway.jpg` or `data/sky.json`. GitHub Pages also tells browsers to keep files for only about ten minutes, so new photos normally show up within that time with a normal reload. If you later switch on Cloudflare's proxy, purge its cache from the Cloudflare dashboard after publishing changes to existing files.

## Data credits
- `data/sky.json` is derived from d3-celestial by Olaf Frohn (BSD-3-Clause, https://github.com/ofrohn/d3-celestial): Hipparcos stars, constellation lines and names.
- `data/milkyway.jpg` is made from the Milky Way background of Deep Star Maps 2020 by NASA's Scientific Visualization Studio (https://svs.gsfc.nasa.gov/4851), tone-mapped and resized to 4096x2048 with RA 0h at the left edge.
- `tools/catalog.json` is derived from OpenNGC by Mattia Verga (CC-BY-SA 4.0, https://github.com/mattiaverga/OpenNGC): object types and Messier and Caldwell numbers.
