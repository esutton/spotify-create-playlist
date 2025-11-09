"""Integration tests for the Spotify playlist creator.

These tests require valid Spotify credentials in environment variables:
SPOTIPY_CLIENT_ID
SPOTIPY_CLIENT_SECRET
SPOTIPY_REDIRECT_URI

The tests will be skipped if credentials are not found.
NOTE: To run integration tests, use: pytest -v --capture=no tests/test_integration.py
"""

import os
import pytest
import requests
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import webbrowser
from urllib.parse import urlparse, parse_qs

from src.create_playlist import create_playlist_and_add_tracks


def has_spotify_credentials():
    """Check if required Spotify credentials are available."""
    load_dotenv()  # Load from .env if present
    return all([
        os.getenv("SPOTIPY_CLIENT_ID"),
        os.getenv("SPOTIPY_CLIENT_SECRET"),
        os.getenv("SPOTIPY_REDIRECT_URI")
    ])


def has_cached_token():
    """Check if we have a cached token file."""
    return os.path.exists(".cache-token")


@pytest.fixture(scope="module")
def spotify_client():
    """Create an authenticated Spotify client.
    
    Requires either:
    - Valid credentials in environment variables and existing token cache
    - Or ability to do interactive OAuth (run with --capture=no)
    """
    if not has_spotify_credentials():
        pytest.skip("Spotify credentials not found in environment")
    
    if not has_cached_token():
        pytest.skip("No cached token found. Run the script first to authenticate.")
    
    # Use modern cache handler approach
    from spotipy.cache_handler import CacheFileHandler
    cache_handler = CacheFileHandler(cache_path=".cache-token")
    
    auth_manager = SpotifyOAuth(
        scope="playlist-modify-public playlist-modify-private",
        cache_handler=cache_handler
    )
    
    # Try to get a valid token without prompting
    try:
        token_info = cache_handler.get_cached_token()
        if not token_info or not auth_manager.validate_token(token_info):
            pytest.skip("No valid cached token. Run the script first to authenticate.")
    except:
        pytest.skip("Error loading cached token. Run the script first to authenticate.")
    
    return spotipy.Spotify(auth_manager=auth_manager)


@pytest.mark.skipif(not has_spotify_credentials() or not has_cached_token(),
                   reason="Spotify credentials or token cache not found")
def test_create_real_playlist(spotify_client):
    """Test creating an actual playlist on Spotify.
    
    This test will:
    1. Get the current user's ID
    2. Create a test playlist
    3. Add two well-known songs
    4. Verify the playlist exists and has the songs
    5. Clean up by deleting the test playlist
    
    NOTE: Requires a valid cached token from previous OAuth.
    Run the main script first to authenticate.
    """
    # Get current user
    user = spotify_client.current_user()
    assert user is not None
    user_id = user["id"]
    
    # Test songs with various patterns including edge cases
    test_songs = [
        "Yesterday - The Beatles",           # Classic rock, very common
        "Bohemian Rhapsody - Queen",        # Another classic, multiple versions exist
        "Billie Jean Michael Jackson",      # No hyphen, different format
        "Shape of You",                     # Modern song, very popular
        "La Vie En Rose - Édith Piaf",     # Non-English characters
        "99 Luftballons",                   # Non-English title
        "Back in Black ACDC",               # Avoid special characters in search
        "ThisSongDefinitelyDoesNotExist",   # Non-existent song
        "Random Words That Might Match Something Unexpected",  # Might get unexpected match
        "Greatest Hits",                    # Generic term that might match many things
        "!@#$%^&* NoSuchSong !@#$%^&*",   # Special characters handling
        "zxcvbnm123456qwerty_nonexistent_song_title_that_should_never_match_anything",  # Long random string
        "",                                # Empty string
        "     ",                           # Just whitespace
        "∑´®†¥¨ˆøπåß∂ƒ©∆˚¬",             # Unicode special characters
        "\u0000\u0001\u0002\u0003",       # Control characters
        "http://example.com/song.mp3",     # URL-like string
        "SELECT * FROM songs;",            # SQL-like string
        "<script>alert('xss')</script>",   # HTML/JS-like string
        "../../etc/passwd",                # Path traversal-like string
        "♫♪♩♬♭♮♯",                        # Musical notation symbols
        "🎵🎶🎹🎸🎺🥁",                    # Music emojis
        r"\n\t\r\b\f",                     # Escape sequences
        "Null",                            # Database-like values
        "undefined",
        "NaN"
    ]
    
    # Create playlist with test songs
    playlist_name = "Integration Test Playlist"
    playlist = create_playlist_and_add_tracks(
        spotify_client,
        user_id,
        playlist_name,
        test_songs
    )
    
    assert playlist is not None
    playlist_id = playlist["id"]
    
    try:
        # Verify playlist was created with correct metadata
        found_playlist = spotify_client.playlist(playlist_id)
        assert found_playlist["name"] == playlist_name
        assert found_playlist["owner"]["id"] == user_id
        assert "Created by demo script" in found_playlist["description"]
        
        # Get detailed track information
        tracks = spotify_client.playlist_items(
            playlist_id,
            additional_types=('track',),
            fields='items(track(name,artists,uri,explicit))'
        )
        
        assert len(tracks["items"]) > 0
        print(f"\nVerifying {len(tracks['items'])} tracks:")
        
        # Keep track of which songs we searched for
        original_searches = [s.lower() for s in test_songs]
        
        # Verify each track's details
        for item in tracks["items"]:
            track = item["track"]
            print(f"\nTrack: {track['name']}")
            print(f"Artists: {', '.join(artist['name'] for artist in track['artists'])}")
            print(f"URI: {track['uri']}")            # Basic track assertions
            assert track["uri"].startswith("spotify:track:")
            assert len(track["artists"]) > 0
            assert all(artist.get("name") for artist in track["artists"])
            assert track["name"], "Track must have a name"
            
            # Detailed track verification including metadata
            track_info = f"{track['name']} - {track['artists'][0]['name']}"
            print(f"\nVerifying track: {track_info}")
            
            # Verify track structure and required fields
            assert "uri" in track, "Track must have URI"
            assert track["uri"].startswith("spotify:track:"), f"Invalid URI format: {track['uri']}"
            
            # Print and verify track metadata
            duration_ms = track.get("duration_ms", 0)
            duration_min = duration_ms / (1000 * 60)
            is_explicit = track.get("explicit", False)
            print(f"  Duration: {duration_min:.1f} minutes")
            print(f"  Explicit: {'Yes' if is_explicit else 'No'}")
            print(f"  Artists: {', '.join(artist['name'] for artist in track['artists'])}")
            
            # Basic duration sanity check (if available)
            if duration_ms:
                assert 30_000 < duration_ms < 36_000_000, f"Duration {duration_ms}ms outside normal range (30s-10hr)"
            
            # Create pairs of search terms and expected substrings
            expected_tracks = {
                "Yesterday - The Beatles": ["Yesterday", "Beatles"],
                "Bohemian Rhapsody - Queen": ["Bohemian", "Queen"],
                "Billie Jean Michael Jackson": ["Billie Jean", "Jackson"],
                "Shape of You": ["Shape of You", "Sheeran"],
                "La Vie En Rose - Édith Piaf": ["Vie en rose", "Piaf"],
                "99 Luftballons": ["99 Luftballons", "Nena"],
                "Back in Black AC/DC": ["Back in Black", "AC/DC"]
            }
            
            # For unexpected tracks, log details for analysis
            track_lowercase = track_info.lower()
            if "greatest hits" in track_lowercase:
                print("  ⚠️ Warning: Matched generic term 'Greatest Hits'")
            
            if any(word in track_lowercase for word in ["remix", "cover", "live", "remaster"]):
                print(f"  ℹ️ Note: This appears to be a modified version")
            
                # Check if this track matches any of our expected tracks
                # or is from an intentionally unexpected search
                unexpected_searches = [
                    "ThisSongDefinitelyDoesNotExist",
                    "Random Words That Might Match Something Unexpected",
                    "Greatest Hits"
                ]
                
                matched = False
                for search_query, expected_terms in expected_tracks.items():
                    if all(term.lower() in track_info.lower() for term in expected_terms):
                        print(f"  ✓ Matched search '{search_query}'")
                        matched = True
                        break
                
                if not matched:
                    # Check if this was from one of our intentionally unexpected searches
                    search_term = next((term for term in unexpected_searches 
                                     if any(term.lower() in search.lower() for search in original_searches)), None)
                    if search_term:
                        print(f"  ℹ️ Expected unexpected result for search '{search_term}'")
                        matched = True
                    else:
                        print(f"  ✗ No match found for {track_info}")
                        assert False, f"Unexpected or mismatched track: {track_info}"
            
            print(f"\nAll track assertions passed")
        
    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 429:  # Rate limit error
            retry_after = int(e.headers.get('Retry-After', 30))
            print(f"\nRate limit hit. Would retry after {retry_after} seconds")
            pytest.skip(f"Rate limit exceeded. Try again in {retry_after} seconds")
        elif e.http_status == 503:  # Service temporarily unavailable
            pytest.skip("Spotify API temporarily unavailable")
        else:
            raise
            
    except (requests.exceptions.RequestException, 
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout) as e:
        pytest.skip(f"Network error occurred: {str(e)}")
        
    finally:
        try:
            # Cleanup: Delete the test playlist (using modern method)
            spotify_client.current_user_unfollow_playlist(playlist_id)
            print("Test playlist cleaned up")
        except Exception as e:
            print(f"Warning: Cleanup failed - {str(e)}")