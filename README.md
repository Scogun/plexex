# PlexEx

PlexEx adds two automation actions to Home Assistant for an existing Plex Media Server connection:

- `plexex.search_movies` — search the movie library by title or title fragment.
- `plexex.mark_unwatched` — mark a movie as unwatched using its Plex `ratingKey`.

PlexEx reuses the URL and token stored by the official Home Assistant Plex integration. It does not ask for Plex credentials again.

## Requirements

- Home Assistant 2026.11 or newer for the built-in Marketplace.
- The official **Plex Media Server** integration configured with the server.

## Setup

After installing PlexEx, go to **Settings → Devices & services → Add integration → PlexEx** and select the existing official Plex server.

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

Fields:

| Field | Type | Description |
|---|---|---|
| `ratingKey` | Integer | Plex library item identifier |
| `title` | String | Movie title |
| `year` | Integer | Release year |
| `viewCount` | Integer | Number of times watched |
| `lastViewedAt` | String or null | Last viewed timestamp |

`lastViewedAt` is `null` if Plex has no last-viewed timestamp.

The `movies` field is already a structured list. No JSON parsing is required.

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

If multiple PlexEx entries are configured, pass the server name:

```yaml
action: plexex.search_movies
data:
  title: Interstellar
  server: Living Room Plex
response_variable: result
```

The name must match the server name shown by the official Plex integration.

The optional `server` field is also supported by `plexex.mark_unwatched`.

## Technical notes

- PlexAPI network calls run in Home Assistant's executor, not in the event loop.
- PlexEx supports movies only.
- PlexEx creates no entities or sensors.
- PlexAPI is supplied by the official Plex integration dependency; PlexEx does not install a second version.

<!-- ha-marketplace:exclude-start -->
## Manual installation

Copy `custom_components/plexex` into `/config/custom_components/plexex/`, restart Home Assistant, then add PlexEx from **Settings → Devices & services**.

## Add as a Marketplace custom repository

If PlexEx is not yet in the default catalog, open **Settings → Marketplace → Add from link** and enter the public GitHub repository URL.
<!-- ha-marketplace:exclude-end -->

## Development

GitHub Actions run Home Assistant `hassfest`, the HACS/Marketplace repository validation action, and Python bytecode compilation on pushes and pull requests.
