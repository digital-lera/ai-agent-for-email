from __future__ import annotations

import json
import re
import smtplib
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from pathlib import Path
from typing import Any

from src.backend.models import ProcessingError


DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "scripts" / "directum_rules.json"


@dataclass(frozen=True)
class DirectumIds:
    signed_by_id: int
    recipient_id: int
    counterparty_id: int


@dataclass(frozen=True)
class RuleAction:
    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleDecision:
    skip_directum: bool = False
    reason: str = ""
    signed_by_id: int | None = None
    recipient_id: int | None = None
    counterparty_id: int | None = None
    forward_to: tuple[str, ...] = ()
    matched_rules: tuple[str, ...] = ()

    def apply_to_ids(self, ids: DirectumIds) -> DirectumIds:
        return DirectumIds(
            signed_by_id=ids.signed_by_id if self.signed_by_id is None else self.signed_by_id,
            recipient_id=ids.recipient_id if self.recipient_id is None else self.recipient_id,
            counterparty_id=(
                ids.counterparty_id if self.counterparty_id is None else self.counterparty_id
            ),
        )


def load_directum_rules(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(str(config.get("directum_rules_path", DEFAULT_RULES_PATH)))
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as rules_file:
            payload = json.load(rules_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ProcessingError(f"Failed to read Directum rules from {path}: {exc}") from exc

    rules = payload.get("rules", payload) if isinstance(payload, dict) else payload
    if not isinstance(rules, list):
        raise ProcessingError("Directum rules file must contain a list or {'rules': [...]}")
    return [rule for rule in rules if isinstance(rule, dict) and rule.get("enabled", True)]


def apply_sender_rules(rules: list[dict[str, Any]], sender: str) -> RuleDecision:
    return apply_email_rules(rules, sender=sender)


def apply_email_rules(
    rules: list[dict[str, Any]],
    *,
    sender: str,
    subject: str = "",
    body: str = "",
    attachment_names: tuple[str, ...] = (),
    recipient_addresses: tuple[str, ...] = (),
) -> RuleDecision:
    sender_email = _email_address(sender)
    recipient_emails = tuple(
        email
        for address in recipient_addresses
        if (email := _email_address(address))
    )
    searchable_text = f"{subject}\n{body}"
    decision = _MutableDecision()
    for rule in rules:
        when = rule.get("when", {})
        if not isinstance(when, dict) or not _matches_email(
            when,
            sender=sender,
            sender_email=sender_email,
            recipient_emails=recipient_emails,
            searchable_text=searchable_text,
            attachment_names=attachment_names,
        ):
            continue
        _apply_actions(rule, decision)
    return decision.freeze()


def apply_id_rules(rules: list[dict[str, Any]], ids: DirectumIds) -> RuleDecision:
    decision = _MutableDecision()
    for rule in rules:
        when = rule.get("when", {})
        if not isinstance(when, dict) or not _matches_ids(when, ids):
            continue
        _apply_actions(rule, decision, ids=ids, when=when)
    return decision.freeze()


from email import policy
from email.parser import BytesParser
from email.message import EmailMessage


def forward_original_email(
    *,
    original_message: bytes,
    original_subject: str,
    sender: str,
    recipients: tuple[str, ...],
    config: dict[str, Any],
) -> None:
    if not recipients:
        return

    server = str(config.get("smtp_server", "")).strip()
    if not server:
        raise ProcessingError(
            "Пересылка письма невозможна: не указан SMTP-сервер в конфигурации"
        )

    username = str(config.get("smtp_username", config.get("username", "")))
    password = str(config.get("smtp_password", config.get("email-password", "")))
    from_address = str(config.get("forward_from", username))
    port = int(config.get("smtp_port", 587))
    use_tls = bool(config.get("smtp_use_tls", True))

    original = BytesParser(policy=policy.default).parsebytes(original_message)

    fwd = EmailMessage()
    fwd["From"] = from_address
    fwd["To"] = ", ".join(recipients)
    fwd["Subject"] = f"Fwd: {original.get('Subject', original_subject)}"

    original_text = original.get_body(preferencelist=("plain", "html"))
    original_payload = original_text.get_content() if original_text else ""

    prefix = (
        "Письмо было автоматически перенаправлено правилом обработки.\n"
        f"Исходный отправитель: {sender}\n\n"
    )

    if original.get_body(preferencelist=("html",)):
        
        fwd.set_content(prefix + (original.get_body(preferencelist=("plain",)) or original_text).get_content())
        html_prefix = prefix.replace("\n", "<br>")

        fwd.add_alternative(
            "<p>{}</p>\n{}".format(
                html_prefix,
                original.get_body(preferencelist=("html",)).get_content(),
            ),
            subtype="html",
        )
    else:
        # только текст
        fwd.set_content(prefix + original_payload)

    # 4. Копируем вложения
    for attachment in original.iter_attachments():
        fwd.add_attachment(
            attachment.get_content(),
            maintype=attachment.get_content_maintype(),
            subtype=attachment.get_content_subtype(),
            filename=attachment.get_filename(),
        )

    # 5. Отправляем по SMTP
    try:
        with smtplib.SMTP(server, port, timeout=int(config.get("smtp_timeout", 30))) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(fwd)
    except (OSError, smtplib.SMTPException) as exc:
        raise ProcessingError(f"Failed to forward email to {recipients}: {exc}") from exc


@dataclass
class _MutableDecision:
    skip_directum: bool = False
    reason: str = ""
    signed_by_id: int | None = None
    recipient_id: int | None = None
    counterparty_id: int | None = None
    forward_to: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)

    def freeze(self) -> RuleDecision:
        return RuleDecision(
            skip_directum=self.skip_directum,
            reason=self.reason,
            signed_by_id=self.signed_by_id,
            recipient_id=self.recipient_id,
            counterparty_id=self.counterparty_id,
            forward_to=tuple(dict.fromkeys(self.forward_to)),
            matched_rules=tuple(self.matched_rules),
        )


def _apply_actions(
    rule: dict[str, Any],
    decision: _MutableDecision,
    *,
    ids: DirectumIds | None = None,
    when: dict[str, Any] | None = None,
) -> None:
    decision.matched_rules.append(str(rule.get("name", "unnamed rule")))
    actions = rule.get("actions", [])
    if not isinstance(actions, list):
        raise ProcessingError(f"Rule {rule.get('name', '<unnamed>')} has invalid actions")

    if "__default__" in rule.get("name")  and len(decision.matched_rules) > 1:
        return

    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("type", ""))
        if action_type == "skip_directum":
            decision.skip_directum = True
            decision.reason = str(action.get("reason", rule.get("name", decision.reason)))
        elif action_type == "replace_matched_id":
            _replace_matched_id(action, decision, ids, when)
        elif action_type == "set_signed_by_id":
            decision.signed_by_id = int(action["id"])
        elif action_type == "set_recipient_id":
            decision.recipient_id = int(action["id"])
        elif action_type == "set_counterparty_id":
            decision.counterparty_id = int(action["id"])
        elif action_type == "forward_email":
            decision.forward_to.extend(_action_recipients(action))


def _replace_matched_id(
    action: dict[str, Any],
    decision: _MutableDecision,
    ids: DirectumIds | None,
    when: dict[str, Any] | None,
) -> None:
    if ids is None or when is None:
        return
    new_id = int(action["id"])
    if "signed_by_id" in when and ids.signed_by_id == int(when["signed_by_id"]):
        decision.signed_by_id = new_id
    if "recipient_id" in when and ids.recipient_id == int(when["recipient_id"]):
        decision.recipient_id = new_id
    if "counterparty_id" in when and ids.counterparty_id == int(when["counterparty_id"]):
        decision.counterparty_id = new_id
    if "any_id" in when:
        any_id = int(when["any_id"])
        if ids.signed_by_id == any_id:
            decision.signed_by_id = new_id
        if ids.recipient_id == any_id:
            decision.recipient_id = new_id
        if ids.counterparty_id == any_id:
            decision.counterparty_id = new_id


def _action_recipients(action: dict[str, Any]) -> list[str]:
    value = action.get("to", [])
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _matches_email(
    when: dict[str, Any],
    *,
    sender: str,
    sender_email: str,
    recipient_emails: tuple[str, ...],
    searchable_text: str,
    attachment_names: tuple[str, ...],
) -> bool:
    supported_keys = {
        "sender_email",
        "sender_contains",
        "recipient_email",
        "recipient_email_any",
        "text_contains_any",
        "attachment_name_contains_any",
    }
    if not any(key in when for key in supported_keys):
        return False
    if "text_contains_any" in when and not _contains_any(
        searchable_text,
        when["text_contains_any"],
    ):
        return False
    if "sender_email" in when and sender_email != str(when["sender_email"]).casefold():
        return False
    if "sender_contains" in when and str(when["sender_contains"]).casefold() not in sender.casefold():
        return False
    if "recipient_email" in when and str(when["recipient_email"]).casefold() not in recipient_emails:
        return False
    if "recipient_email_any" in when and not _recipient_email_any(
        recipient_emails,
        when["recipient_email_any"],
    ):
        return False
    
    if "attachment_name_contains_any" in when and not _attachment_name_contains_any(
        attachment_names,
        when["attachment_name_contains_any"],
    ):
        return False
    return True


def _contains_any(value: str, needles: Any) -> bool:
    terms = needles if isinstance(needles, list) else [needles]
    normalized = value.casefold()
    return any(_contains_term(normalized, str(term).casefold()) for term in terms)


def _contains_term(value: str, term: str) -> bool:
    if term in value:
        return True
    if len(term) <= 2:
        return term in _tokens(value)
    return any(_is_fuzzy_match(token, term) for token in _tokens(value))


def _tokens(value: str) -> list[str]:
    return re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", value.casefold())


def _is_fuzzy_match(value: str, term: str) -> bool:
    if abs(len(value) - len(term)) > 2:
        return False
    return SequenceMatcher(None, value, term).ratio() >= 0.82


def _attachment_name_contains_any(names: tuple[str, ...], needles: Any) -> bool:
    return any(_contains_any(Path(name).stem, needles) for name in names)


def _recipient_email_any(recipient_emails: tuple[str, ...], needles: Any) -> bool:
    terms = needles if isinstance(needles, list) else [needles]
    normalized_terms = {str(term).casefold() for term in terms}
    return any(email in normalized_terms for email in recipient_emails)


def _matches_ids(when: dict[str, Any], ids: DirectumIds) -> bool:
    checks = {
        "signed_by_id": ids.signed_by_id,
        "recipient_id": ids.recipient_id,
        "counterparty_id": ids.counterparty_id,
    }
    matched = False
    for key, current_id in checks.items():
        if key in when:
            matched = matched or current_id == int(when[key])
    if "any_id" in when:
        any_id = int(when["any_id"])
        matched = matched or any_id in {
            ids.signed_by_id,
            ids.recipient_id,
            ids.counterparty_id,
        }
    return matched


def _email_address(value: str) -> str:
    addresses = getaddresses([value])
    if addresses:
        return addresses[0][1].casefold()
    return parseaddr(value)[1].casefold()
