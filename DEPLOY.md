# Publishing the EFRS Workload Monitor

The app is a Flask + pandas backend. Two facts shape how you publish it:

1. **The 315 MB dataset CSV cannot go to GitHub** (100 MB file limit). It doesn't need to —
   the server runs entirely from the committed **49 MB cleaned cache** `app/.cache_v5.pkl`.
2. **Use a Python host** (Render, Railway, Fly.io). Static hosts like Vercel/Netlify
   can't run the Python backend.

The app has been verified to run cache-only (no CSV) at ~192 MB peak — fits the free tier.

---

## Recommended: GitHub → Render

### 1. Put it on GitHub
```bash
cd <the project folder>
git init
git add .gitignore render.yaml DEPLOY.md app/
git commit -m "EFRS Workload Monitor — deployable app"
git branch -M main
git remote add origin https://github.com/<you>/efrs-workload-monitor.git
git push -u origin main
```
The `.gitignore` keeps the 49 MB cache and excludes the 315 MB CSV, `__pycache__`, and
`app/logs/`. Confirm the cache is staged: `git status` should list `app/.cache_v5.pkl`
(GitHub's warning threshold is 50 MB — 49 MB sits just under it).

### 2. Deploy on Render
- Create a free account at render.com → **New → Web Service** → connect your repo.
- Render reads `render.yaml` automatically (root dir `app`, Python, gunicorn).
  If configuring by hand instead:
  - **Root directory:** `app`
  - **Build:** `pip install -r requirements.txt`
  - **Start:** `gunicorn server:app --preload --workers 1 --timeout 120 --bind 0.0.0.0:$PORT`
- Click **Deploy**. First build takes a few minutes; you get a public URL like
  `https://efrs-workload-monitor.onrender.com`.

A push to `main` rebuilds and redeploys automatically — the repository is the deploy button.

---

## Governance (one human review before anything reaches users)
Protect `main` so every change passes one human review before it reaches users:
- Work on a branch, open a **pull request**, review, then merge to `main` (which deploys).
- On a free/private repo where branch protection isn't enforceable, give collaborators
  **read-only** access and have them contribute via fork + PR that you merge.
- Keep a **deployment log** of episodes, overrides, and outside reactions during the
  week of real use.

---

## Updating the data later
The committed cache is a frozen snapshot. To refresh:
1. Locally, replace the CSV in `Dataset/`, delete `app/.cache_v5.pkl`, run `python server.py`
   once (rebuilds the cache), then commit the new `app/.cache_v5.pkl` and push.
2. Or call `/api/refresh` (wired to the live SODA API, dataset `7hsn-idqi`): it appends newer rows and re-caches in place. On free hosting the refreshed cache sits on ephemeral disk, so for a durable snapshot, commit the rebuilt cache instead.

## Notes
- Free Render instances sleep after inactivity; the first hit after idle is slow (cold start).
- `app/logs/refusal_log.csv` is git-ignored; on Render it lives on ephemeral disk. For a
  durable audit trail, add a Render persistent disk or log to a database.
