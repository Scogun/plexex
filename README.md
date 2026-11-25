# PlexEx

PlexEx extends an existing Plex Media Server connection with automation actions and a Plex Pass status sensor:

- `plexex.search_movies` — search the movie library by title or title fragment.
- `plexex.mark_unwatched` — mark a movie as unwatched using its Plex `ratingKey`.
- `plexex.skip_marker` — seek a Plex player past the intro, credits, or commercial break it is playing.
- A diagnostic binary sensor that reports whether the Plex account has an active Plex Pass subscription.
- A **Playback event** event entity that reports when playback of a movie or an episode enters or leaves a Plex marker: intro, credits, final credits, or commercial. There is one entity for the whole server and one for each Plex player. Each event type is also fired as a Home Assistant event, for example `plexex_final_credits_started`.

PlexEx reuses the URL and token stored by the official Home Assistant Plex integration. It does not ask for Plex credentials again.

## Requirements

- Home Assistant 2026.11 or newer.
- The official **Plex Media Server** integration configured with the server.

## Installation

<!-- ### Install from the Home Assistant Marketplace catalog

1. Open **Settings → Marketplace**.
2. Search for **PlexEx**.
3. Open the PlexEx repository page and select **Install**.
4. Complete the integration setup by selecting the existing official Plex server. -->

### Install as a custom repository

Use these steps while PlexEx is not yet available in the default Marketplace catalog.

1. Open **Settings → Marketplace**.
2. Select **Add from link** in the upper-right corner.
3. In **GitHub link**, enter:
   ```text
   https://github.com/Scogun/plexex
   ```
4. Select **Add**. If Home Assistant asks for the content type, choose **Integration** and confirm.
5. Open the added **PlexEx** repository and select **Install**.
6. Complete the integration setup by selecting the existing official Plex server.

Adding a custom repository requires connecting a GitHub account to the Marketplace. Home Assistant uses this connection to read the public GitHub repository.

### Configure PlexEx

After installation, add PlexEx from **Settings → Devices & services → Add integration → PlexEx** and select the existing official Plex server.

Add one PlexEx config entry for each Plex server you want to use.

## Actions

### `plexex.search_movies`

Searches the Plex movie library by full or partial title.

The action returns structured response data and can be used with `response_variable`.

```yaml
sequence:
  - action: plexex.search_movies
    data:
      title: Harry Potter
    response_variable: result

  - repeat:
      for_each: "{{ result.movies }}"
      sequence:
        - action: persistent_notification.create
          data:
            title: Plex search
            message: "{{ repeat.item.title }} ({{ repeat.item.year }})"
```

Response structure:

```yaml
movies:
  - ratingKey: 12345
    title: Harry Potter and the Philosopher's Stone
    year: 2001
    viewCount: 1
    lastViewedAt: "2025-12-25T20:15:00"
```

| Field | Type | Description |
|---|---|---|
| `ratingKey` | Integer | Plex library item identifier |
| `title` | String | Movie title |
| `year` | Integer | Release year |
| `viewCount` | Integer | Number of times watched |
| `lastViewedAt` | String or null | Last viewed timestamp |

`lastViewedAt` is `null` if Plex has no last-viewed timestamp. The `movies` field is already a structured list; no JSON parsing is required.

### `plexex.mark_unwatched`

Marks a Plex library item as unwatched.

```yaml
action: plexex.mark_unwatched
data:
  rating_key: 12345
```

Use the integer `ratingKey` returned by `plexex.search_movies`.

### Example: Search and mark all matching movies as unwatched

```yaml
alias: Mark matching Plex movies as unwatched
fields:
  title:
    name: Movie title
    required: true
    selector:
      text:

sequence:
  - action: plexex.search_movies
    data:
      title: "{{ title }}"
    response_variable: result

  - repeat:
      for_each: "{{ result.movies }}"
      sequence:
        - action: plexex.mark_unwatched
          data:
            rating_key: "{{ repeat.item.ratingKey }}"
```

### `plexex.skip_marker`

Seeks a Plex player to the end of the marker it is playing right now: an intro, credits, or a commercial break.

```yaml
action: plexex.skip_marker
data:
  entity_id: media_player.plex_plex_for_apple_tv_living_room
```

| Field | Required | Description |
|---|---|---|
| `entity_id` | Yes | Media player created by the official Plex integration |
| `markers` | No | Kinds of markers to skip: `intro`, `credits`, `final_credits`, `commercial`. Any marker is skipped when empty |

The action fails if the player is not inside a marker (or not inside one of the selected kinds), so it is safe to call from a button. The seek itself is done by the official Plex integration through `media_player.media_seek`, so the player has to support seeking; Plex Web and other clients that cannot be controlled remotely do not. Skipping the final credits seeks to their end, which is usually the end of the item.

This action has no `server` field: PlexEx finds the server from the media player.

### Example: Skip intros automatically

This automation skips every intro on every player. The trigger is the PlexEx bus event, which carries the player's entity ID:

```yaml
alias: Skip Plex intros
triggers:
  - trigger: event
    event_type: plexex_intro_started
actions:
  - action: plexex.skip_marker
    data:
      entity_id: "{{ trigger.event.data.player_id }}"
      markers:
        - intro
```

## Multiple Plex servers

If multiple PlexEx entries are configured, select the connection in the action's **Server** field. In YAML, `server` is the PlexEx config entry ID selected by the action selector:

```yaml
action: plexex.search_movies
data:
  title: Interstellar
  server: YOUR_PLEXEX_CONFIG_ENTRY_ID
response_variable: result
```

The same optional `server` field is available for `plexex.mark_unwatched`. Leave it empty if only one PlexEx connection is configured.

## Plex Pass sensor

Each PlexEx config entry creates a diagnostic binary sensor named **Plex Pass**. It is on when the Plex server reports an active Plex Pass; this is read from the server itself. Its attributes include the Plex username, subscription plan, and subscription features. These come from plex.tv using the server's token and are empty when the token cannot be used there, for example on a local server without a token. Everything is refreshed hourly.

## Playback marker triggers

PlexEx listens for state updates from media players created by the official Plex integration. When a movie or an episode starts playing, it fetches and caches the item's markers. Between position updates, it estimates playback locally from `media_position` and `media_position_updated_at` and checks the estimate once per second; it does not poll Plex sessions. When the estimated position moves into or out of a marker, it fires a Home Assistant event and updates the PlexEx **Playback event** entity.

Markers are created by Plex itself when it analyzes the library (intro and credits detection are Plex Pass features). PlexEx does not guess: an item without markers produces no events.

### Event types

| Event type | Fires when playback |
|---|---|
| `intro_started` | enters an intro |
| `intro_ended` | plays past the end of an intro |
| `credits_started` | enters credits that are not the final ones, for example before a post-credits scene |
| `credits_ended` | plays past the end of those credits |
| `final_credits_started` | enters the final credits (the marker Plex flags with `final="1"`) |
| `final_credits_ended` | plays past the end of the final credits |
| `commercial_started` | enters a commercial break of a recording |
| `commercial_ended` | plays past the end of a commercial break |

A credits marker is reported either as `credits_*` or as `final_credits_*`, never both. To react to any credits, list both event types in the trigger. Final credits usually run to the end of the item, so `final_credits_ended` is rare: stopping playback is not reported as an end.

### React to one player

PlexEx adds a **Playback event** entity to the device of every media player created by the official Plex integration, for example `event.plex_plex_for_apple_tv_living_room_playback_event`. It only receives events from that player. In the automation editor, choose the **Event received** trigger, target the player's device (or its **Playback event** entity), and select `final_credits_started`:

```yaml
triggers:
  - trigger: event.received
    target:
      device_id: YOUR_PLEX_PLAYER_DEVICE_ID
    options:
      event_type:
        - final_credits_started
```

Entities follow the official Plex integration: a new player gets its entity when Plex creates its media player, and the entity is removed together with the media player. Plex Web and other transient players share a single **Plex Client Service** device, so their entities are added to the PlexEx server device instead and carry the player's name.

### React to any player

The **Playback event** entity on the PlexEx server device receives events from every player of that server. Target the PlexEx device to use it:

```yaml
triggers:
  - trigger: event.received
    target:
      device_id: YOUR_PLEXEX_DEVICE_ID
    options:
      event_type:
        - final_credits_started
```

Every event type is also fired on the Home Assistant event bus with the `plexex_` prefix, for example `plexex_intro_started`.

### Event data

| Field | Description |
|---|---|
| `server` | PlexEx config entry ID (bus event only) |
| `rating_key` | Plex library item identifier |
| `media_type` | `movie` or `episode` |
| `title` | Movie or episode title |
| `show_title`, `season`, `episode` | Show name, season number, and episode number; `null` for movies |
| `marker_type` | Plex marker type: `intro`, `credits`, or `commercial` |
| `final` | `true` for the final credits marker |
| `marker_start`, `marker_end` | Marker boundaries in milliseconds |
| `view_offset` | Estimated playback position in milliseconds when the event fired |
| `user` | Plex username |
| `player_name` | Player name |
| `player_id` | Entity ID of the Plex media player |
| `player` | Deprecated: same value as `player_name`; will be removed in 0.9.0 |

To filter a bus event by player, match on `player_id`:

```yaml
triggers:
  - trigger: event
    event_type: plexex_final_credits_started
    event_data:
      player_id: media_player.plex_plex_for_apple_tv_living_room
```

### How seeking and resuming are handled

- Seeking forward into a marker counts as entering it. Seeking over a whole marker, or backward into one, fires nothing.
- A playback that begins inside a marker fires its `*_started` event. This covers intros that start at the very beginning of an episode, and also an item resumed in the middle of its credits.
- If playback is already inside a marker when PlexEx starts, PlexEx establishes a baseline and does not fire `*_started` for it.
- Moving the position while paused only moves the baseline; resuming inside a marker after that fires nothing.

## Technical notes

- PlexAPI network calls run in Home Assistant's executor, not in the event loop.
- `plexex.search_movies` covers movies only. Marker events cover movies and TV episodes.
- PlexEx creates one diagnostic binary sensor for each configured Plex server.
- PlexAPI is supplied by the official Plex integration dependency; PlexEx does not install a second version.

## Development and releases

Pull requests are checked by the validation workflow. When changes are merged into `main`, the release workflow runs the same checks. If all checks pass, it reads `version` from `custom_components/plexex/manifest.json`, creates a Git tag with that exact version, and publishes a GitHub Release.

To publish a new version, update the `version` field in `manifest.json` before merging the change into `main`. The release workflow fails if that tag already exists.
