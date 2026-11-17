"""Read verified generations from a dedicated private GitHub repository."""
from base64 import b64decode
from datetime import datetime
from hashlib import sha256
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

POLICY = "5b28c591c4282a13686035404a200a441d0fccbfaadec4be98dbd39a832554d2"
PUBLIC_REPO = "shadrinavlada9-cmyk/facecode-wb-analytics"
MAX_BYTES = 25 * 1024 * 1024
HASH = re.compile(r"[0-9a-f]{64}\Z")
PAYLOAD_KEYS = {
    "released_at_utc", "funnel_days", "accepted_weeks", "coverage_by_scope", "values", "products",
    "sku_gt10_by_article", "ad_history", "xway_detail", "classification_stale", "conflict_count", "unresolved_count",
}


class Denied(Exception):
    """Credentials or repository privacy cannot be verified."""


class Unavailable(Exception):
    """The service could not be reached."""


class Invalid(Exception):
    """The stored object is missing or inconsistent."""


class Missing(Invalid):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def checksum(data):
    return sha256(data).hexdigest()


def object_json(data):
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError):
        raise Invalid from None
    if not isinstance(value, dict):
        raise Invalid
    return value


def verify_pointer(data):
    value = object_json(data)
    if set(value) != {"current", "previous"}:
        raise Invalid
    for item in (value["current"], value["previous"]):
        if item is None and value["previous"] is None:
            continue
        if not isinstance(item, str) or not HASH.fullmatch(item):
            raise Invalid
    if not value["current"] or value["current"] == value["previous"]:
        raise Invalid
    return value


def coverage_summary(payload):
    return {"days": len(payload["funnel_days"]), "last_day": max(payload["funnel_days"]),
            "accepted_weeks": payload["accepted_weeks"]}


def verify_generation(data, generation):
    if checksum(data) != generation:
        raise Invalid
    value = object_json(data)
    if set(value) != {"manifest", "analytics"}:
        raise Invalid
    manifest, payload = value["manifest"], value["analytics"]
    try:
        if set(payload) != PAYLOAD_KEYS or set(manifest) != {
            "schema", "policy", "payload_sha256", "updated_at", "coverage", "controls",
        }:
            raise Invalid
        if manifest["schema"] != 1 or manifest["policy"] != POLICY or manifest["payload_sha256"] != checksum(canonical(payload)):
            raise Invalid
        if manifest["updated_at"] != payload["released_at_utc"] or manifest["coverage"] != coverage_summary(payload):
            raise Invalid
        if datetime.fromisoformat(manifest["updated_at"]).utcoffset() is None:
            raise Invalid
        if not isinstance(manifest["controls"], dict):
            raise Invalid
        for key in ("values", "funnel_days", "coverage_by_scope", "accepted_weeks", "xway_detail",
                    "sku_gt10_by_article", "ad_history"):
            if not isinstance(payload[key], list):
                raise Invalid
        if not isinstance(payload["products"], dict) or any(
            not isinstance(row, list) or len(row) != 4 or not isinstance(row[3], dict) for row in payload["values"]
        ):
            raise Invalid
    except (ValueError, TypeError, KeyError):
        raise Invalid from None
    return payload


def generation_path(generation):
    if not isinstance(generation, str) or not HASH.fullmatch(generation):
        raise Invalid
    return f"generations/{generation}.json"


class GitHubStore:
    def __init__(self, repository, token):
        if (not isinstance(repository, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repository, re.ASCII)
                or repository.casefold() == PUBLIC_REPO.casefold() or any(x in {".", ".."} for x in repository.split("/"))
                or not isinstance(token, str) or not token.strip() or not token.isascii()
                or any(c.isspace() for c in token)):
            raise Denied
        self.repository = repository
        self._token = token
        self._http = build_opener(NoRedirect())

    def request(self, suffix="", *, media="application/vnd.github+json", body=None, method=None):
        url = f"https://api.github.com/repos/{self.repository}{suffix}"
        headers = {"Accept": media, "Authorization": f"Bearer {self._token}", "User-Agent": "FACE-CODE-Analytics",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            with self._http.open(Request(url, data=body, headers=headers, method=method), timeout=8) as response:
                data = response.read(MAX_BYTES + 1)
        except HTTPError as exc:
            if exc.code == 404:
                raise Missing from None
            if exc.code in (408, 429) or exc.code >= 500 or (exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0"):
                raise Unavailable from None
            raise Denied from None
        except (URLError, OSError):
            raise Unavailable from None
        if len(data) > MAX_BYTES:
            raise Invalid
        return data

    def verify_private(self):
        try:
            repo = object_json(self.request())
        except Missing:
            raise Denied from None
        if (repo.get("private") is not True or repo.get("visibility") != "private"
                or str(repo.get("full_name")).casefold() != self.repository.casefold()):
            raise Denied

    def read(self, path):
        return self.request(f"/contents/{path}?ref=main", media="application/vnd.github.raw+json")

    def pointer_blob(self):
        try:
            doc = object_json(self.request("/contents/current.json?ref=main"))
        except Missing:
            return None, None
        if doc.get("encoding") != "base64" or not re.fullmatch(r"[0-9a-f]{40}", str(doc.get("sha"))):
            raise Invalid
        try:
            return verify_pointer(b64decode(doc["content"])), doc["sha"]
        except (ValueError, KeyError, TypeError):
            raise Invalid from None


def latest(store):
    store.verify_private()
    try:
        pointer = verify_pointer(store.read("current.json"))
    except Missing:
        raise Denied from None
    for generation in (pointer["current"], pointer["previous"]):
        if generation:
            try:
                return verify_generation(store.read(generation_path(generation)), generation), generation != pointer["current"]
            except (Invalid, Unavailable):
                if generation == (pointer["previous"] or pointer["current"]):
                    raise
    raise Invalid
