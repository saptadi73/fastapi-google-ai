# Celery production services (Ubuntu)

These units use the same deployment directory and Unix account as `api-google.service`. The application reads `.env` from its project root. Install **one beat instance** per deployment; the worker may be scaled separately after testing.

Before enabling the services, inspect queued jobs. Starting beat will dispatch all queued work, including duplicate registration jobs. On 8 October 2026 the production queue already contained more than 20 `DISCOVER` jobs from several users, including two for duplicate source `product_2`. The original `product` source was discovered successfully with seven tabs. Review the current queue and decide how to handle duplicates before starting beat.

```bash
cd /var/www/fastapi_app/fastapi-google-ai
sudo install -m 0644 deploy/systemd/api-google-celery-worker.service /etc/systemd/system/
sudo install -m 0644 deploy/systemd/api-google-celery-beat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/api-google-celery-{worker,beat}.service
sudo systemctl enable --now api-google-celery-worker.service api-google-celery-beat.service
systemctl status api-google-celery-worker.service api-google-celery-beat.service --no-pager
```

Check dispatch and execution in separate logs:

```bash
journalctl -u api-google-celery-beat.service -u api-google-celery-worker.service -n 100 --no-pager
```

`/health/ready` reports that Redis is reachable. It does not check whether worker or beat is running. Confirm that a queued job reaches `SUCCEEDED` or `FAILED` via `/api/v1/jobs/{job_id}`.
