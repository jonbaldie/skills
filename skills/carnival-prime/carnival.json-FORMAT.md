# `.carnival.json` format

Optional file in the project cwd. `/carnival-prime` reads it when present.
Missing file → defaults below. Invalid or unknown fields → ignore those fields;
do not invent harness APIs.

This config is **advisory**. Carnival is skill-driven and agent-agnostic: the
model honours what it can through the harness's own session/subagent controls.

## Fields

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `maxHands` | number | unbounded | Soft cap on concurrent Hand agents |
| `maxRiggers` | number | unbounded | Soft cap on concurrent Rigger agents |
| `maxSpotters` | number | `1` | Soft cap on concurrent Spotter agents |
| `model` | string | harness default | Preferred model id/name when slinging |
| `thinking` | string | harness default | Preferred thinking/reasoning level when slinging |

## Example

```json
{
  "maxHands": 3,
  "maxRiggers": 1,
  "maxSpotters": 1,
  "model": "claude-opus-4",
  "thinking": "high"
}
```
