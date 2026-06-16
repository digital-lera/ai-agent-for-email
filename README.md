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
  "request_timeout": 30,
  "max_attachment_bytes": 52428800,
  "ocr_gpu": true,
  "ocr_workers": 0,
  "ocr_confidence": 0.5,
  "ocr_dpi": 200,
  "ocr_heartbeat_seconds": 15,
  "directum_rules_path": "src/scripts/directum_rules.json",
  "smtp_server": "smtp.example",
  "smtp_port": 587,
  "smtp_use_tls": true
}
```

All Directum RX requests use `verify=False` because this deployment's API
requires TLS certificate verification to be disabled.

`ocr_gpu` defaults to `true`. The application container is configured with an
NVIDIA GPU reservation and EasyOCR refuses to silently fall back to CPU. At
startup it prints the PyTorch version, bundled CUDA runtime, CUDA availability,
GPU name, VRAM, compute capability, and cuDNN version. `OCR_CUDA_DEVICE`
selects the GPU index and defaults to `0`.

The host CUDA/driver version and the CUDA runtime bundled with PyTorch do not
need to have the same minor version. The NVIDIA driver must support the runtime
reported by `torch.version.cuda`. During every page, OCR prints a heartbeat
every `ocr_heartbeat_seconds`.

Each email is processed in an isolated directory under `src/scripts/jobs`.
The message is moved to the processed IMAP folder only after OCR, AI
validation, Directum document creation, and all attachment uploads succeed.
Failed messages are flagged for manual processing and produce a Directum task.

## Directum processing rules

Rules that change or bypass Directum processing live in
`src/scripts/directum_rules.json`. The file is regular JSON and can be edited
without changing Python code.

Each rule has:

- `name`: human-readable label for logs.
- `enabled`: set to `false` to temporarily disable a rule.
- `when`: the condition.
- `actions`: one or more actions to apply when the condition matches.

Supported conditions:

- `sender_email`: exact sender email match, case-insensitive.
- `sender_contains`: text contained in the full `From` header.
- `text_contains_any`: fuzzy match against the subject and email body.
- `attachment_name_contains_any`: fuzzy match against attachment names without
  extensions.
- `signed_by_id`: Directum contact ID after lookup.
- `recipient_id`: Directum employee ID after lookup.
- `counterparty_id`: Directum counterparty ID after lookup.
- `any_id`: matches signed-by, recipient, or counterparty ID.

Supported actions:

- `skip_directum`: do not create an incoming letter in Directum. For email-level
  rules, this also stops AI/OCR processing.
- `replace_matched_id`: replace whichever ID matched the condition.
- `set_signed_by_id`: force a specific `SignedBy` ID.
- `set_recipient_id`: force a specific `Addressee` ID.
- `set_counterparty_id`: force a specific correspondent ID.
- `forward_email`: send the original email as an `.eml` attachment.

Example:

```json
{
  "name": "Forward letters for recipient 608",
  "enabled": true,
  "when": {
    "recipient_id": 608
  },
  "actions": [
    {
      "type": "forward_email",
      "to": "StryginaVM@taif.ru"
    },
    {
      "type": "skip_directum",
      "reason": "Recipient 608 is handled by email forwarding"
    }
  ]
}
```

Forwarding rules require SMTP settings in `login.json`. By default the service
uses `username` and `email-password` for SMTP login; override them with
`smtp_username`, `smtp_password`, or `forward_from` if needed.

Daily processing statistics are stored in `src/data/statistics.sqlite3` using
the `Europe/Moscow` calendar date. The timezone can be changed with the
`STATISTICS_TIMEZONE` environment variable. Counters are idempotent by email
Message-ID, so polling the same email again does not increment it twice.

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
