"""Free LLM calls for WarWatch (docs/ACCURACY_PROPOSAL.md, section 4). Standard library only.

Two free providers behind one function, each pinned to an exact model so a record never mixes models without saying so:
    gemini  Google AI Studio free tier   secret GEMINI_API_KEY, optional variable GEMINI_MODEL
    groq    Groq free plan               secret GROQ_API_KEY,   optional variable GROQ_MODEL

    ask(text, "groq") -> (answer text, exact model version)

Free-tier limits are per day and per minute and can change without notice; a 429 is retried with a wait, then raised, so a caller can
stop for the day and resume later.
"""
import json
import os
import time
import urllib.error
import urllib.request

PROVIDERS = {
    "gemini": {"key": "GEMINI_API_KEY", "model_var": "GEMINI_MODEL", "model": "gemini-3.5-flash-lite", "pause": 6.0},
    # gpt-oss-120b: knowledge cutoff June 2024 (OpenAI model card), so news after that date is new to it. Free plan: 8,000 tokens a minute
    # and 200,000 a day; an event-desk call is about 5,000 tokens with the answer, so one a minute and about 40 a day.
    "groq": {"key": "GROQ_API_KEY", "model_var": "GROQ_MODEL", "model": "openai/gpt-oss-120b", "pause": 50.0},
}
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"
UA = "warwatch/0.3 (public-data research; github.com/khourix/warwatch)"


class DailyLimit(Exception):
    """The provider still refuses after the retries: treat the day's quota as spent."""


def model_for(provider):
    p = PROVIDERS[provider]
    return os.environ.get(p["model_var"]) or p["model"]


def key_for(provider):
    return os.environ.get(PROVIDERS[provider]["key"], "")


def _post(url, body, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": UA, **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _gemini(text, model, key, post):
    body = {"contents": [{"role": "user", "parts": [{"text": text}]}], "generationConfig": {"temperature": 0, "maxOutputTokens": 4096}}
    r = post(GEMINI_API.format(m=model), body, {"x-goog-api-key": key})
    c = (r.get("candidates") or [{}])[0]
    out = "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", []) if not p.get("thought"))
    return out, r.get("modelVersion") or model


def _groq(text, model, key, post):
    body = {"model": model, "messages": [{"role": "user", "content": text}], "temperature": 0, "max_completion_tokens": 4096}
    if "gpt-oss" in model:
        body["reasoning_effort"] = "low"
    r = post(GROQ_API, body, {"Authorization": "Bearer " + key})
    msg = ((r.get("choices") or [{}])[0].get("message") or {})
    return msg.get("content") or "", r.get("model") or model


def ask(text, provider, model=None, key=None, post=_post, sleep=time.sleep, tries=3):
    """-> (answer text, model version). Raises DailyLimit when 429s outlast the retries; other HTTP errors propagate."""
    model = model or model_for(provider)
    key = key if key is not None else key_for(provider)
    if not key:
        raise RuntimeError(f"{PROVIDERS[provider]['key']} is not set")
    call = _gemini if provider == "gemini" else _groq
    for attempt in range(tries):
        try:
            return call(text, model, key, post)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            if attempt == tries - 1:
                raise DailyLimit(f"{provider} {model}: 429 after {tries} tries") from e
            wait = 30 * (attempt + 1)
            try:
                wait = max(wait, float(e.headers.get("retry-after") or 0))
            except (AttributeError, TypeError, ValueError):
                pass
            sleep(min(wait, 120))
    raise DailyLimit(provider)
