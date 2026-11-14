AUTO-UPDATES
============
Friends run start.ps1 (Windows PowerShell) or start.py (any system with Python:  python start.py). Each launch it checks your
published copy of the game and downloads only the files that changed. If they're offline, or
anything goes wrong, the game just starts the version they already have.
In-game, the version shows bottom-right, and a banner appears if a newer version is published
while they're playing.

ONE-TIME SETUP (you)
1. Create a free PUBLIC GitHub repository (e.g. "battlefront") and upload this whole folder to it
   (GitHub web page: "Add file" > "Upload files", drag the folder contents in).
2. Open update.json and replace OWNER/REPO with your GitHub name and repo, e.g.
      "manifestUrl": "https://raw.githubusercontent.com/PhantomOverrideX/War-Funder/main/manifest.json"
3. Upload update.json too, zip this folder, and send that zip to your friends ONCE.

EVERY TIME YOU CHANGE THE GAME
1. Run:   python make_release.py        (rewrites manifest.json with the new version + file hashes)
2. Upload/push the changed files AND manifest.json to the repo.
Friends get it next time they launch (GitHub can take a few minutes to refresh).

NOTES
- update.json is never overwritten by an update, so each friend keeps their own source address.
- Launcher scripts (start.ps1 / start.py) aren't auto-updated; if one ever changes,
  friends need to re-download. Everything else (game, textures, updater.py) updates itself.
- Anything you publish will run on your friends' computers, so only publish files you trust and
  keep your repo's login secure. Downloads are checked against the SHA-256 hashes in manifest.json
  and the update is skipped if any file doesn't match.
- Friends' saves (progress, decals) live in their browser and aren't touched by updates.
