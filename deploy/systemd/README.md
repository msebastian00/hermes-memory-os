# Hermes Memory HTTP systemd draft

This unit is prepared for Spark 2 after manual semantic smoke checks pass. It does not store API keys; keep `HERMES_MEMORY_HTTP_API_KEY=...` in the ignored `.env.http.local` file.

Manual install, when ready:

```bash
sudo cp deploy/systemd/hermes-memory-http.service /etc/systemd/system/hermes-memory-http.service
sudo systemctl daemon-reload
sudo systemctl start hermes-memory-http.service
sudo systemctl status hermes-memory-http.service
```

Enable on boot only after another health/search smoke passes:

```bash
sudo systemctl enable hermes-memory-http.service
```

Expected health:

```json
{"ok":true,"semantic_ready":true,"degraded":false,"degraded_reasons":[]}
```
