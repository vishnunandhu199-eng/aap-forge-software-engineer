# GitHub + Render deployment guide

## 1. Initialize Git

Run these commands in the project folder:

```bash
git init
git add .
git commit -m "Initial App Forge release"
```

## 2. Create a GitHub repository

1. Open GitHub and create a new repository.
2. Copy the repository URL.
3. Link the local repo:

```bash
git branch -M main
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

## 3. Deploy to Render

1. Sign in to Render.
2. Click New + and choose Web Service.
3. Connect your GitHub repository.
4. Select the repository you just pushed.
5. Use these settings:
   - Runtime: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn python.app:app`
6. Add an environment variable:
   - Name: `FLASK_SECRET_KEY`
   - Value: any strong secret string
7. Click Create Web Service.

Render will build and deploy the app automatically.

## 4. Local development

```bash
python -m pip install -r requirements.txt
python python/app.py
```

Then open it in your web browser:

```text
http://127.0.0.1:5000
```
