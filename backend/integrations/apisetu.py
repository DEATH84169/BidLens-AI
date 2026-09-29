"""Contract-configured API Setu transport; no guessed universal endpoint/schema.

Use only the server administrator's approved publisher specification. This is
integration infrastructure, not a certified or live-tested publisher adapter.
"""

import hashlib
import json
import os
from urllib.parse import urlsplit
import httpx
from storage import now


def pointer(value, path):
    if not path.startswith("/"):
        raise ValueError("Expected JSON pointer")
    for part in path[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def config():
    path = os.getenv("APISETU_CONFIG_PATH")
    if not path:
        return {}
    with open(path, encoding="utf-8") as stream:
        result = json.load(stream)
    if not isinstance(result, dict):
        raise ValueError("Invalid configuration")
    return result


def verify(check, identifier, mode="live", transport=None):
    result = {
        "status": "NOT_VERIFIED",
        "source": None,
        "checked_at": None,
        "attempted_at": now(),
        "environment": mode,
        "reason": "No approved publisher configuration or credentials.",
        "authoritative": False,
    }
    if mode == "demo":
        return {
            **result,
            "status": "SIMULATED",
            "reason": "Synthetic demonstration; no registry contacted.",
        }
    try:
        cfg = config().get(check)
        if not cfg:
            return result
        url = cfg["url"]
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 443)
            or not any(
                parsed.hostname == h or parsed.hostname.endswith("." + h)
                for h in ("apisetu.gov.in", "api-setu.in")
            )
        ):
            raise ValueError("Unapproved host")
        environment = cfg["environment"]
        if environment not in ("sandbox", "production"):
            raise ValueError("Invalid environment")
        if mode == "live" and environment != "production":
            return {
                **result,
                "reason": "Only sandbox is configured; live verification unavailable.",
            }
        if mode == "sandbox" and environment != "sandbox":
            return {**result, "reason": "No sandbox subscription configured."}
        if "sandbox" in parsed.hostname and environment == "production":
            raise ValueError("Sandbox cannot be production")
        method = cfg["method"].upper()
        if method not in ("GET", "POST"):
            raise ValueError("Unsupported lookup method")
        headers = {
            name: os.environ[env_name]
            for name, env_name in cfg["headers_from_env"].items()
        }
        if not headers or not all(headers.values()):
            return result
        params = dict(cfg.get("fixed_parameters", {}))
        params[cfg["identifier_parameter"]] = identifier
        # No documents or manufactured consent assertions are forwarded.
        with httpx.Client(
            timeout=10, follow_redirects=False, transport=transport, trust_env=False
        ) as client:
            response = client.request(
                method,
                url,
                headers=headers,
                **({"params": params} if method == "GET" else {"json": params}),
            )
        result.update(
            source=cfg["publisher"],
            source_url=url,
            environment=environment,
            checked_at=now(),
            http_status=response.status_code,
            response_sha256=hashlib.sha256(response.content).hexdigest(),
        )
        if response.status_code != 200:
            return {
                **result,
                "reason": "Provider unavailable or denied access; no verification established.",
            }
        if len(response.content) > 2_000_000:
            return {**result, "reason": "Provider response exceeded accepted size."}
        body = response.json()
        returned_id = pointer(body, cfg["response_identifier_pointer"])
        if (
            not isinstance(returned_id, str)
            or returned_id.strip().upper() != identifier.strip().upper()
        ):
            return {
                **result,
                "reason": "Response did not match the requested identifier.",
            }
        status = pointer(body, cfg["response_status_pointer"])
        if status in cfg["verified_values"]:
            outcome = "VERIFIED"
        elif status in cfg.get("failed_values", []):
            outcome = "FAILED"
        else:
            return {
                **result,
                "reason": "Unmapped response status; manual review required.",
            }
        return {
            **result,
            "status": "SIMULATED" if environment == "sandbox" else outcome,
            "authoritative": environment == "production",
            "provider_status": status,
            "reason": "Publisher response matched this identifier and this check only.",
        }
    except (OSError, ValueError, KeyError, TypeError, IndexError, httpx.HTTPError):
        return {
            **result,
            "reason": "Configuration, network or response validation failed; manual review required.",
        }
