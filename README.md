# PlexEx

PlexEx adds two automation actions to Home Assistant for an existing Plex Media Server connection:

- `plexex.search_movies` — search the movie library by title or title fragment.
- `plexex.mark_unwatched` — mark a movie as unwatched using its Plex `ratingKey`.

PlexEx reuses the URL and token stored by the official Home Assistant Plex integration. It does not ask for Plex credentials again.

## Requirements

- Home Assistant 2026.11 or newer.
- The official **Plex Media Server** integration configured with the server.

## Installation

### Install from the Home Assistant Marketplace catalog

1. Open **Settings → Marketplace**.
2. Search for **PlexEx**.
3. Open the PlexEx repository page and select **Install**.
4. Complete the integration setup by selecting the existing official Plex server.

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

If multiple PlexEx entries are configured, pass the server name:

```yaml
action: plexex.search_movies
data:
  title: Interstellar
  server: Living Room Plex
response_variable: result
```

The name must match the server name shown by the official Plex integration. The optional `server` field is also supported by `plexex.mark_unwatched`.

## Technical notes

- PlexAPI network calls run in Home Assistant's executor, not in the event loop.
- PlexEx supports movies only.
- PlexEx creates no entities or sensors.
- PlexAPI is supplied by the official Plex integration dependency; PlexEx does not install a second version.

## Development and releases

Pull requests are checked by the validation workflow. When changes are merged into `main`, the release workflow runs the same checks. If all checks pass, it reads `version` from `custom_components/plexex/manifest.json`, creates a Git tag with that exact version, and publishes a GitHub Release.

To publish a new version, update the `version` field in `manifest.json` before merging the change into `main`. The release workflow fails if that tag already exists.
