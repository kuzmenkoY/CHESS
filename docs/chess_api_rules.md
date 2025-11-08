# Chess.com API Rules & Best Practices

## Essential Requirements

### User-Agent Header
**REQUIRED**: Always include a User-Agent header with contact information.
```python
HEADERS = {
    "User-Agent": "YourApp/1.0 (contact@example.com)"
}
```
- Helps identify your application
- Required for proper API access
- Include contact info so Chess.com can reach you if issues arise

### Rate Limiting
- **Serial requests**: Unlimited (wait for response before next request)
- **Parallel requests**: May receive `429 Too Many Requests`
- **Best practice**: Make requests sequentially, not in parallel
- Handle `429` responses gracefully with retry logic

## HTTP Response Codes

| Code | Meaning | Action |
|------|---------|--------|
| `200` | Success | Use the JSON data |
| `301` | Redirect | Update URL for future requests |
| `304` | Not Modified | Use cached data |
| `404` | Not Found | Invalid URL or resource doesn't exist |
| `410` | Gone | Resource permanently unavailable - stop requesting |
| `429` | Too Many Requests | Rate limited - wait and retry |

## Caching

- **Cache invalidation**: Endpoints refresh at most once every 12-24 hours
- **ETag/Last-Modified**: Use `If-None-Match` and `If-Modified-Since` headers for efficient caching
- **304 responses**: Safe to use cached data when received
- **Cache-Control**: Respect `max-age` values in responses

## Data Currency

- **Not guaranteed current**: ~3% of players on old v2 site may cause stale data
- **Refresh rate**: Maximum once per 12-24 hours
- **Mobile apps**: Not affected by v2/v3 data sync issues

## Best Practices

### Request Format
```python
import requests

BASE_URL = "https://api.chess.com/pub"
HEADERS = {
    "User-Agent": "YourApp/1.0 (contact@example.com)"
}

response = requests.get(f"{BASE_URL}/player/{username}", headers=HEADERS, timeout=10)
```

### Error Handling
- Always check `response.status_code` before parsing JSON
- Handle `429` with exponential backoff
- Don't retry `410` responses
- Use timeouts (recommended: 10 seconds)

### Compression
- API supports `gzip` compression
- Include `Accept-Encoding: gzip` header (usually automatic)
- Can save up to 80% bandwidth

### JSON-LD
- Responses include JSON-LD context links
- Check `Link` header for context URL
- Fully compatible with standard JSON parsing

## Important Notes

- **Read-only**: Cannot send moves or commands via this API
- **Public data only**: No private data (game chat, conditional moves)
- **English responses**: All text responses in English
- **Timestamps**: Unix epoch (seconds since Jan 1, 1970)

## Example Endpoints

- Profile: `https://api.chess.com/pub/player/{username}`
- Stats: `https://api.chess.com/pub/player/{username}/stats`
- Archives: `https://api.chess.com/pub/player/{username}/games/archives`
- Monthly Games: `https://api.chess.com/pub/player/{username}/games/{YYYY}/{MM}`

## Game Result Codes

Common codes: `win`, `checkmated`, `agreed`, `repetition`, `timeout`, `resigned`, `stalemate`, `lose`, `insufficient`, `abandoned`

