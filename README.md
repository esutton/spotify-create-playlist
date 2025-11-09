# Spotify Create Playlist Demo

This small demo shows how to create a Spotify playlist with three well-known songs using the Spotify Web API and Spotipy (Python client).

Files created
- `src/create_playlist.py` — main demo script (interactive OAuth handled by Spotipy).
- `requirements.txt` — pinned runtime dependencies.
- `.env.example` — environment variable template.
- `tests/test_create_playlist.py` — small unit test that runs without Spotify credentials.

Setup

1. Create a Spotify application at https://developer.spotify.com/dashboard and obtain:
   - CLIENT ID
   - CLIENT SECRET
   - Redirect URI (for example `http://localhost:8888/callback`)

2. Copy `.env.example` to `.env` and set your credentials (or set env vars directly):

```bash
cp .env.example .env
# edit .env and fill values
```

3. Install dependencies (use a virtualenv):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the demo

```bash
python src/create_playlist.py
```

The script will open a browser for authorization (Spotipy's OAuth flow). It will create a new playlist in your Spotify account and add three well-known songs by searching for them and adding the top search result.

Run tests

Unit tests (no Spotify credentials needed):
```bash
pytest -q tests/test_create_playlist.py
```

Integration tests (requires Spotify credentials and auth):
```bash
# First run the script normally to authenticate:
python src/create_playlist.py

# Then run integration tests (with OAuth output enabled):
pytest -v --capture=no tests/test_integration.py
```

Using a Secure Redirect URI with ngrok

If Spotify requires HTTPS for your redirect URI, you can use ngrok to create a secure tunnel:

1. Install ngrok from https://ngrok.com/download

2. Start an ngrok tunnel on port 8888 (or your chosen port):
```bash
ngrok http 8888
```

3. Copy the HTTPS URL that ngrok displays (e.g., `https://abc123.ngrok.io`)

4. In your Spotify Developer Dashboard:
   - Go to your app settings
   - Add a new Redirect URI: `https://abc123.ngrok.io/callback`
   - Save the changes

5. Update your `.env` file to use the ngrok URL:
```bash
SPOTIPY_REDIRECT_URI=https://abc123.ngrok.io/callback
```

6. Run the script as normal - it will use the secure ngrok tunnel for OAuth.

Security Considerations

1. Credentials and Tokens
   - Never commit `.env` or token cache files to version control
   - The `.gitignore` already excludes `.env` and `.cache-token`
   - Rotate client secrets if they're ever exposed
   - For production apps, store refresh tokens securely (not in files)

2. OAuth Security
   - Use HTTPS redirect URIs in production (see ngrok section above)
   - Consider using PKCE flow instead of client secrets for distributed apps
   - Keep redirect URI registered in Spotify Dashboard in sync with your `.env`
   - Validate state parameter (Spotipy handles this automatically)

3. Local Development
   - The token cache (`.cache-token`) contains sensitive data - keep it private
   - When using ngrok:
     - Tunnel URLs are public - don't share them
     - Each session gets a new URL - update Spotify Dashboard accordingly
     - Consider ngrok authentication for team development
   - Use a dedicated Spotify app for development, separate from production

4. Best Practices
   - Follow Spotify API rate limits
   - Implement proper token refresh and error handling in production
   - Use environment variables or secure secret management, not hardcoded values
   - Regular security audits of dependencies (npm audit, safety check)

Notes and next steps
- This demo uses Spotipy's Authorization Code flow (handled by `SpotifyOAuth`).
- For production, store tokens and refresh securely and follow Spotify's rate limits.
- The `tests/` folder contains a minimal test that doesn't require Spotify credentials.
- When using ngrok, remember the tunnel URL changes each time you restart ngrok.

