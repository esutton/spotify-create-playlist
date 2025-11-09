"""
Simple demo script that creates a Spotify playlist and adds three well-known songs.

This script uses Spotipy's `SpotifyOAuth` to run an Authorization Code flow and will open
a browser window for you to log in and grant permissions. Credentials are read from
environment variables (use a `.env` file with python-dotenv or export them manually).

Helpful comments are included to explain the steps.
"""

import os
import sys
from typing import List

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Default songs to add to the playlist. We search for each string and add the top result.
DEFAULT_SONG_QUERIES = [
    "Bohemian Rhapsody - Queen",
    "Imagine - John Lennon",
    "Billie Jean - Michael Jackson",
]

# Spotify scopes we need: create/modify playlists
SCOPE = "playlist-modify-public playlist-modify-private"


def get_track_queries(songs: List[str]) -> List[str]:
    """Return the list of search queries used to locate tracks on Spotify.

    This helper is simple now, but isolating it makes it easier to test.
    """
    return songs


def create_playlist_and_add_tracks(sp: spotipy.Spotify, user_id: str, playlist_name: str, song_queries: List[str]):
    """Create a playlist for the given user and add the first search result for each query.

    Args:
        sp: Authenticated Spotipy client.
        user_id: Spotify user id (string) where playlist will be created.
        playlist_name: Name of the new playlist.
        song_queries: List of search query strings to find tracks.

    Returns:
        playlist dict returned by Spotify (or None if creation failed).
    """
    # Create the playlist (public by default here) and add a small description
    print(f"Creating playlist '{playlist_name}' for user {user_id}...")
    playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=True,
                                       description="Created by demo script")

    # For each query, search for a track and collect its URI
    track_uris = []
    for q in song_queries:
        print(f"Searching for: {q}")
        # Skip empty or whitespace-only queries
        if not q or not q.strip():
            print("  Skipping empty query")
            continue
            
        try:
            result = sp.search(q, type="track", limit=1)
            items = result.get("tracks", {}).get("items", [])
            if items:
                track = items[0]
                uri = track["uri"]
                artist_names = ", ".join(a["name"] for a in track.get("artists", []))
                print(f"  Found: {track['name']} — {artist_names} (adding)")
                track_uris.append(uri)
            else:
                print(f"  No results for query: {q}")
        except spotipy.exceptions.SpotifyException as e:
            print(f"  Error searching for '{q}': {str(e)}")

    if track_uris:
        # Add found tracks to the playlist
        sp.playlist_add_items(playlist_id=playlist["id"], items=track_uris)
        print("Tracks added to playlist.")
    else:
        print("No tracks found; playlist created but empty.")

    return playlist


def main():
    # Load environment variables from .env if present
    load_dotenv()

    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")
    playlist_name = os.getenv("PLAYLIST_NAME") or "Demo Playlist from Script"

    # Basic check for required credentials. Spotipy will still raise errors if token exchange fails.
    if not client_id or not client_secret or not redirect_uri:
        print("Missing one of SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI in env.")
        print("Copy .env.example to .env and fill in the values, or set the variables in your shell.")
        sys.exit(1)

    # Set up modern cache handler and OAuth manager
    from spotipy.cache_handler import CacheFileHandler
    cache_handler = CacheFileHandler(cache_path=".cache-token")
    
    # Set up Spotipy's OAuth manager with the cache handler
    auth_manager = SpotifyOAuth(client_id=client_id,
                              client_secret=client_secret,
                              redirect_uri=redirect_uri,
                              scope=SCOPE,
                              open_browser=True,
                              cache_handler=cache_handler)

    # Create a Spotipy client using the auth manager.
    sp = spotipy.Spotify(auth_manager=auth_manager)

    # Get current user ID for playlist ownership
    user = sp.current_user()
    user_id = user.get("id")
    if not user_id:
        print("Could not determine current user ID from Spotify API response.")
        sys.exit(1)

    # Prepare queries and create the playlist
    queries = get_track_queries(DEFAULT_SONG_QUERIES)
    playlist = create_playlist_and_add_tracks(sp, user_id, playlist_name, queries)

    if playlist:
        url = playlist.get("external_urls", {}).get("spotify")
        print(f"Playlist created: {url}")
    else:
        print("Playlist creation failed.")


if __name__ == "__main__":
    main()
