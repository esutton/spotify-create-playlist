import pytest
from unittest.mock import Mock, patch
from src.create_playlist import get_track_queries, create_playlist_and_add_tracks, DEFAULT_SONG_QUERIES


def test_get_track_queries_returns_same_list():
    songs = ["Song A", "Song B"]
    assert get_track_queries(songs) == songs


@pytest.fixture
def mock_spotify():
    """Create a mock Spotify client with expected method calls."""
    mock = Mock()
    
    # Mock user_playlist_create
    mock.user_playlist_create.return_value = {
        "id": "playlist123",
        "external_urls": {"spotify": "https://open.spotify.com/playlist/123"}
    }
    
    # Mock search to return a track for each query
    def mock_search(q, type, limit):
        return {
            "tracks": {
                "items": [{
                    "uri": f"spotify:track:{q.replace(' ', '')}",
                    "name": q,
                    "artists": [{"name": "Artist"}]
                }]
            }
        }
    
    mock.search.side_effect = mock_search
    
    # Mock playlist_add_items
    mock.playlist_add_items.return_value = None
    
    return mock


def test_create_playlist_success(mock_spotify):
    """Test successful playlist creation and track addition."""
    playlist = create_playlist_and_add_tracks(
        mock_spotify,
        "user123",
        "Test Playlist",
        ["Song1", "Song2"]
    )
    
    # Verify playlist was created
    mock_spotify.user_playlist_create.assert_called_once_with(
        user="user123",
        name="Test Playlist",
        public=True,
        description="Created by demo script"
    )
    
    # Verify searches were performed
    assert mock_spotify.search.call_count == 2
    mock_spotify.search.assert_any_call("Song1", type="track", limit=1)
    mock_spotify.search.assert_any_call("Song2", type="track", limit=1)
    
    # Verify tracks were added
    mock_spotify.playlist_add_items.assert_called_once()
    added_tracks = mock_spotify.playlist_add_items.call_args[1]["items"]
    assert len(added_tracks) == 2
    assert "spotify:track:Song1" in added_tracks
    assert "spotify:track:Song2" in added_tracks


def test_create_playlist_no_tracks_found(mock_spotify):
    """Test playlist creation when no tracks are found."""
    # Mock search to return empty results
    def mock_empty_search(q, type, limit):
        return {"tracks": {"items": []}}
    
    mock_spotify.search.side_effect = mock_empty_search
    
    playlist = create_playlist_and_add_tracks(
        mock_spotify,
        "user123",
        "Test Playlist",
        ["NonexistentSong1", "NonexistentSong2"]
    )
    
    # Verify playlist was created
    mock_spotify.user_playlist_create.assert_called_once()
    
    # Verify searches were attempted
    assert mock_spotify.search.call_count == 2
    
    # Verify no tracks were added (empty list)
    mock_spotify.playlist_add_items.assert_not_called()


def test_default_song_queries_not_empty():
    """Verify we have default songs to add."""
    assert len(DEFAULT_SONG_QUERIES) > 0
    assert all(isinstance(q, str) for q in DEFAULT_SONG_QUERIES)
    assert all(len(q.strip()) > 0 for q in DEFAULT_SONG_QUERIES)


@patch('spotipy.Spotify')
def test_create_playlist_empty_song_list(mock_spotify):
    """Test creating a playlist with an empty song list."""
    playlist = create_playlist_and_add_tracks(
        mock_spotify,
        "user123",
        "Empty Playlist",
        []
    )
    
    # Playlist should be created but no searches or additions
    mock_spotify.user_playlist_create.assert_called_once()
    mock_spotify.search.assert_not_called()
    mock_spotify.playlist_add_items.assert_not_called()


def test_create_playlist_with_duplicate_songs(mock_spotify):
    """Test adding duplicate songs to a playlist."""
    playlist = create_playlist_and_add_tracks(
        mock_spotify,
        "user123",
        "Duplicate Songs",
        ["Song1", "Song1", "Song1"]  # Same song three times
    )
    
    # Should search three times but add unique URIs
    assert mock_spotify.search.call_count == 3
    added_tracks = mock_spotify.playlist_add_items.call_args[1]["items"]
    assert len(added_tracks) == 3  # We allow duplicates as the user might want them


def test_create_playlist_with_special_characters(mock_spotify):
    """Test creating a playlist with special characters in names."""
    special_name = "Test & Playlist ! @#$%"
    special_song = "Song with & and !"
    
    playlist = create_playlist_and_add_tracks(
        mock_spotify,
        "user123",
        special_name,
        [special_song]
    )
    
    # Verify special characters were handled
    mock_spotify.user_playlist_create.assert_called_once_with(
        user="user123",
        name=special_name,
        public=True,
        description="Created by demo script"
    )
    mock_spotify.search.assert_called_once_with(special_song, type="track", limit=1)


def test_create_playlist_handles_api_error(mock_spotify):
    """Test error handling when Spotify API calls fail."""
    mock_spotify.user_playlist_create.side_effect = Exception("API Error")
    
    with pytest.raises(Exception):
        create_playlist_and_add_tracks(
            mock_spotify,
            "user123",
            "Test Playlist",
            ["Song1"]
        )


def test_create_playlist_with_various_search_results(mock_spotify):
    """Test handling of various search scenarios: found, not found, and unexpected results."""
    def mock_varied_search(q, type, limit):
        search_results = {
            "ExistingSong": {
                "tracks": {
                    "items": [{
                        "uri": "spotify:track:existing123",
                        "name": "ExistingSong",
                        "artists": [{"name": "Expected Artist"}],
                        "duration_ms": 180000,
                        "explicit": False
                    }]
                }
            },
            "UnexpectedResult": {
                "tracks": {
                    "items": [{
                        "uri": "spotify:track:unexpected456",
                        "name": "Completely Different Song",
                        "artists": [{"name": "Different Artist"}],
                        "duration_ms": 240000,
                        "explicit": True
                    }]
                }
            },
            "NonexistentSong": {
                "tracks": {"items": []}
            },
            "MultipleResults": {
                "tracks": {
                    "items": [
                        {
                            "uri": "spotify:track:first789",
                            "name": "First Match",
                            "artists": [{"name": "Artist One"}]
                        },
                        {
                            "uri": "spotify:track:second012",
                            "name": "Second Match",
                            "artists": [{"name": "Artist Two"}]
                        }
                    ]
                }
            }
        }
        return search_results.get(q, {"tracks": {"items": []}})
    
    mock_spotify.search.side_effect = mock_varied_search
    
    # Test with a mix of scenarios
    playlist = create_playlist_and_add_tracks(
        mock_spotify,
        "user123",
        "Mixed Results Playlist",
        [
            "ExistingSong",          # Will find exact match
            "NonexistentSong",       # Will find nothing
            "UnexpectedResult",      # Will find different song
            "MultipleResults"        # Will find multiple matches
        ]
    )
    
    # Verify search was called for each song
    assert mock_spotify.search.call_count == 4
    
    # Verify only found tracks were added
    mock_spotify.playlist_add_items.assert_called_once()
    added_tracks = mock_spotify.playlist_add_items.call_args[1]["items"]
    
    # Should have 3 tracks (exact match, unexpected result, and first of multiple)
    assert len(added_tracks) == 3
    assert "spotify:track:existing123" in added_tracks
    assert "spotify:track:unexpected456" in added_tracks
    assert "spotify:track:first789" in added_tracks


def test_create_playlist_empty_results_handling(mock_spotify):
    """Test handling when all searches return no results."""
    # Reset mock's state
    mock_spotify.reset_mock()
    
    # Mock search to always return empty results
    def mock_empty_search(q, type, limit):
        print(f"Mock search for '{q}' returning no results")
        return {"tracks": {"items": []}}
    
    mock_spotify.search.side_effect = mock_empty_search
    
    playlist = create_playlist_and_add_tracks(
        mock_spotify,
        "user123",
        "Empty Results Playlist",
        ["Song1", "Song2", "Song3"]
    )
    
    # Verify searches were attempted
    assert mock_spotify.search.call_count == 3
    
    # Verify playlist was created but no tracks were added
    mock_spotify.user_playlist_create.assert_called_once()
    mock_spotify.playlist_add_items.assert_not_called()
