# TAIF-mail
*AI tool for organizing corporate email inbox and refining email messages' key content*

**🎉 [v0.1.0 pre-release](https://github.com/digital-lera/ai-agent-for-email/releases/tag/0.1.0) is out!**

## Runtime configuration

Create `src/scripts/login.json` locally. The file is ignored by Git and must
contain:

```json
{
  "username": "service-account",
  "email-password": "mail-password",
  "password": "directum-password",
  "odataurl": "https://directum.example/odata",
  "performer_id": 123,
  "imap_server": "ukexch.uktaif.ru",
  "processed_folder": "AI",
  "verify_tls": true,
  "request_timeout": 30,
  "max_attachment_bytes": 52428800
}
```

`verify_tls` defaults to `true`. Disable it only for a controlled development
environment with a known self-signed certificate.

Each email is processed in an isolated directory under `src/scripts/jobs`.
The message is moved to the processed IMAP folder only after OCR, AI
validation, Directum document creation, and all attachment uploads succeed.
Failed messages are flagged for manual processing and produce a Directum task.

## Local verification

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 -m pytest
```

## Key features to add for the next release:

 ### 🧮 Interface
 - Dashboard with email data refinement history
 - Progress bars for every step of the refining process
 - WebSocket push notifications
 - Logs output window
 - Adjustable interval for inbox updates polling
 
 ### 🎼 Automatization
 - Parallel refinement and task queue using Celery + Redis
 - *Retry*-logic for failures
 - Errors logged into a database

 ### ⚒️ Data refinement
 - Deeper dive into PaddleOCR features, such as built-in key data selection
 - Additional log option with OCR results .png (color-coded)
 - Multiple models fallback for more accurate results
 - Adding message's subject, sender and raw text to the prompts

 ### 💼 Directum integration
 - Migrating for RPA-operated Directum integration to using DirectumRX API (C#)
 - Generating a notification object for operators when results are dubious
 - Auto-generated "queue number" replies for senders

 ### 🔑 Security
 - Add a secrets manager
 - All text data encoding on transit and storage
 - Logs anonymization

 ### 🚀 Deployment
 - Docker Compose
 - Monitoring with Prometheus + Grafana
 - GitHub CI/CD

 ### 🧪 Testing
 - End-to-end tests on a bigger number of samples
 - Load testing
 - Documentation
