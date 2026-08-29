import re
import time
from collections import Counter
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


from flask import Blueprint, jsonify, request

websitedna = Blueprint("websitedna", __name__)

REQUEST_TIMEOUT = 6
MAX_CSS_FILES = 6
MAX_CSS_BYTES = 400_000
USER_AGENT = (
    "Mozilla/5.0 (compatible; WebsiteDNABot/1.0; "
    "+https://fun.theorangecow.org/websitedna)"
)


HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB_COLOR_RE = re.compile(
    r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*[\d.]+\s*)?\)"
)
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}]+)")

NEUTRAL_HEXES = {"#ffffff", "#fff", "#000000", "#000", "#transparent"}


def normalize_hex(h):
    h = h.lower()
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    return h


def rgb_to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(int(r), int(g), int(b))


def is_grayscale(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return max(r, g, b) - min(r, g, b) < 12


def extract_colors(css_text, counter):
    for m in HEX_COLOR_RE.finditer(css_text):
        counter[normalize_hex(m.group(0))] += 1
    for m in RGB_COLOR_RE.finditer(css_text):
        counter[rgb_to_hex(*m.groups())] += 1


def extract_fonts(css_text, counter):
    for m in FONT_FAMILY_RE.finditer(css_text):
        raw = m.group(1)
        first = raw.split(",")[0].strip().strip("'\"")
        if first and first.lower() not in ("inherit", "initial", "unset"):
            counter[first] += 1


def fetch(url, timeout=REQUEST_TIMEOUT):
    return requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )


@websitedna.route("/analyze")
def analyze():
    target = request.args.get("url", "").strip()
    if not target:
        return jsonify({"error": "missing url parameter"}), 400

    if not re.match(r"^https?://", target, re.I):
        target = "https://" + target

    parsed = urlparse(target)
    if not parsed.netloc:
        return jsonify({"error": "invalid url"}), 400

    started = time.time()

    try:
        resp = fetch(target)
    except requests.RequestException as e:
        return (
            jsonify({"error": f"could not reach that site ({e.__class__.__name__})"}),
            502,
        )

    if resp.status_code >= 400:
        return jsonify({"error": f"site responded with {resp.status_code}"}), 502

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    title = (
        soup.title.string.strip() if soup.title and soup.title.string else parsed.netloc
    )
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = (
        desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else ""
    )

    color_counter = Counter()
    font_counter = Counter()

    style_tags = soup.find_all("style")
    for tag in style_tags:
        css = tag.get_text() or ""
        extract_colors(css, color_counter)
        extract_fonts(css, font_counter)

    link_tags = [
        l
        for l in soup.find_all("link", rel=lambda v: v and "stylesheet" in v.lower())
        if l.get("href")
    ][:MAX_CSS_FILES]

    fetched_css_files = 0
    for link in link_tags:
        css_url = urljoin(target, link["href"])
        try:
            css_resp = fetch(css_url, timeout=4)
            if css_resp.status_code < 400:
                css_text = css_resp.text[:MAX_CSS_BYTES]
                extract_colors(css_text, color_counter)
                extract_fonts(css_text, font_counter)
                fetched_css_files += 1
        except requests.RequestException:
            continue

    ranked_colors = sorted(
        color_counter.items(),
        key=lambda kv: (is_grayscale(kv[0]), -kv[1]),
    )
    top_colors = [c for c, _ in ranked_colors[:5]]
    if not top_colors:
        top_colors = ["#cccccc"]

    top_fonts = [f for f, _ in font_counter.most_common(3)]

    script_count = len(soup.find_all("script"))
    stylesheet_count = len(link_tags) + len(style_tags)
    page_kb = round(len(html.encode("utf-8")) / 1024, 1)

    elapsed_ms = round((time.time() - started) * 1000)

    return jsonify(
        {
            "url": target,
            "domain": parsed.netloc,
            "title": title,
            "description": description,
            "colors": top_colors,
            "fonts": (
                top_fonts
                if top_fonts
                else ["not detectable (styles likely injected by JS)"]
            ),
            "stats": {
                "page_kb": page_kb,
                "script_tags": script_count,
                "stylesheets_found": stylesheet_count,
                "css_files_fetched": fetched_css_files,
                "colors_found": len(color_counter),
                "analysis_ms": elapsed_ms,
            },
        }
    )


@websitedna.route("/")
def health():
    return jsonify({"status": "ok", "usage": "/analyze?url=https://example.com"})
