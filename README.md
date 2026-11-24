# PlexEx

PlexEx extends an existing Plex Media Server connection with automation actions and a Plex Pass status sensor:

- `plexex.search_movies` — search the movie library by title or title fragment.
- `plexex.mark_unwatched` — mark a movie as unwatched using its Plex `ratingKey`.
- A diagnostic binary sensor that reports whether the Plex account has an active Plex Pass subscription.
- A **Playback event** event entity with the **final_credits_started** event type when playback enters a movie's final credits marker. The integration also fires the `plexex_final_credits_started` Home Assistant event.

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

## Final credits trigger

PlexEx listens for state updates from media players created by the official Plex integration. When a movie starts playing, it fetches and caches that movie's final credits marker. On each media-player update, PlexEx compares the new `media_position` with the previous one. When the reported position crosses the marker start, it fires the `plexex_final_credits_started` Home Assistant event and updates the PlexEx **Playback event** entity. In the automation editor, choose the **Event received** trigger, target the PlexEx device, and select `final_credits_started`:

```yaml
triggers:
  - trigger: event.received
    target:
      device_id: YOUR_PLEXEX_DEVICE_ID
    options:
      event_type:
        - final_credits_started
```

The event data includes `server` (PlexEx config entry ID), `rating_key`, `title`, `view_offset`, `marker_start`, `marker_end`, `user`, and `player`. Time offsets are milliseconds. The event is emitted only when Plex provides a final credits marker (`final="1"`); it is not inferred from every `credits` marker. If playback is already inside the marker when PlexEx starts, PlexEx establishes a baseline and does not fire an event for that playback.

## Technical notes

- PlexAPI network calls run in Home Assistant's executor, not in the event loop.
- PlexEx supports movies only.
- PlexEx creates one diagnostic binary sensor for each configured Plex server.
- PlexAPI is supplied by the official Plex integration dependency; PlexEx does not install a second version.

## Development and releases

Pull requests are checked by the validation workflow. When changes are merged into `main`, the release workflow runs the same checks. If all checks pass, it reads `version` from `custom_components/plexex/manifest.json`, creates a Git tag with that exact version, and publishes a GitHub Release.

To publish a new version, update the `version` field in `manifest.json` before merging the change into `main`. The release workflow fails if that tag already exists.
