"""PlexEx constants."""
DOMAIN = "plexex"
PLEX_DOMAIN = "plex"
CONF_PLEX_ENTRY_ID = "plex_entry_id"
CONF_SERVER = "server"
SERVICE_SEARCH = "search"
SERVICE_SEARCH_MOVIES = "search_movies"
SERVICE_MARK_UNWATCHED = "mark_unwatched"
SERVICE_SKIP_MARKER = "skip_marker"

# Library item types plexex.search can look for.
SEARCH_TYPES = ("movie", "show", "season", "episode")

# Marker types reported by Plex. A credits marker Plex flags as final is
# reported as its own kind, so the last credits can be told from earlier ones.
MARKER_TYPE_CREDITS = "credits"
MARKER_TYPES = ("intro", MARKER_TYPE_CREDITS, "commercial")
MARKER_KIND_FINAL_CREDITS = "final_credits"
MARKER_KINDS = (*MARKER_TYPES, MARKER_KIND_FINAL_CREDITS)
MARKER_STARTED = "started"
MARKER_ENDED = "ended"

# Event types of the playback event entity, e.g. "intro_started". Each one is
# also fired on the Home Assistant bus with the domain prefix, e.g.
# "plexex_intro_started".
PLAYBACK_EVENT_TYPES = tuple(
    f"{kind}_{phase}"
    for kind in MARKER_KINDS
    for phase in (MARKER_STARTED, MARKER_ENDED)
)
EVENT_PREFIX = f"{DOMAIN}_"
