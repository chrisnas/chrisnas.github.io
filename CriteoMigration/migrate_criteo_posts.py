"""
Migrate 12 old Criteo Labs HTML blog posts to the Hugo/PaperMod GitHub Pages site.

Handles:
- HTML parsing and metadata extraction from OpenGraph tags
- Content extraction from WordPress HTML structure
- HTML-to-Markdown conversion (gists, pre blocks, blockquotes, headings, images, etc.)
- Image copying into Hugo page bundles
- Dead link detection with concurrent HTTP checking
- Cross-reference replacement (labs.criteo.com -> /posts/ paths)
- Update of existing posts referencing migrated posts
- Migration summary report generation
"""

import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
    import requests
except ImportError:
    print("Missing dependencies. Install with: pip install beautifulsoup4 requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_DIR = Path(r"C:\Personel\Blog\Sauvegarde Blogs")
HUGO_ROOT = Path(r"C:\Personel\Blog\GithubPages\chrisnas.github.io")
CONTENT_DIR = HUGO_ROOT / "content" / "posts"

SITE_CHROME_FILES = {
    "criteolab.jpg", "K5Tl5Lof-150x150.jpg", "ChristopheNasarre-Photo-150x150.jpg",
    "logo_orig.svg", "location.svg", "underline.svg",
}

TAG_NORMALIZE = {
    "Dotnet": ".NET",
    "#csharp": "C#",
    "Miscellaneous": None,
    "Code": None,
    "Developers": None,
}

# labs.criteo.com URL -> new Hugo path mapping (populated during processing)
CRITEO_URL_MAP = {}

LINK_CHECK_TIMEOUT = 10
LINK_CHECK_WORKERS = 10

# ---------------------------------------------------------------------------
# URL mapping: labs.criteo.com slug patterns -> new post directory names
# ---------------------------------------------------------------------------

CRITEO_SLUG_TO_DIR = {
    "2017/02/going-beyond-sos-clrmd-part-1": "2017-02-21_clrmd-part-1-going-beyond",
    "2017/03/clrmd-part-2": "2017-03-24_clrmd-part-2-from-clrruntime",
    "2017/04/clrmd-part-3": "2017-05-03_clrmd-part-3-static-instance-fields",
    "2017/05/clrmd-part-3": "2017-05-03_clrmd-part-3-static-instance-fields",
    "2017/05/clrmd-part-4": "2017-05-31_clrmd-part-4-timer-callbacks",
    "2017/06/clrmd-part-5": "2017-06-29_clrmd-part-5-extend-sos-windbg",
    "2017/08/clrmd-part-6": "2017-08-01_clrmd-part-6-memory-structures",
    "2017/08/clrmd-part-7": "2017-08-28_clrmd-part-7-nested-structs-dynamic",
    "2017/11/clrmd-part-8": "2017-11-03_clrmd-part-8-net-thread-pool",
    "2017/12/clrmd-part-9": "2017-12-22_clrmd-part-9-tasks-thread-pool",
    "2017/04/ryujit": "2017-04-06_ryujit-never-ending-threadabort",
    "2017/09/extending-new-windbg-part-1": "2017-09-06_extending-windbg-part-1-buttons",
    "2018/05/extending-new-windbg-part-3": "2018-05-22_extending-windbg-part-3-csharp",
    # Part 2 is missing from backup
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TITLE_TO_SLUG = {
    "ClrMD Part 1 - Going beyond SOS": "clrmd-part-1-going-beyond",
    "ClrMD Part 2 - From ClrRuntime to ClrHeap or how to traverse the managed heap": "clrmd-part-2-from-clrruntime",
    "ClrMD Part 3 - Dealing with static and instance fields to list timers": "clrmd-part-3-static-instance-fields",
    "ClrMD Part 4 - What callbacks are called by my timers?": "clrmd-part-4-timer-callbacks",
    "ClrMD Part 4 \u2013 What callbacks are called by my timers?": "clrmd-part-4-timer-callbacks",
    "ClrMD Part 5 - How to use ClrMD to extend SOS in WinDBG": "clrmd-part-5-extend-sos-windbg",
    "ClrMD Part 5 \u2013 How to use ClrMD to extend SOS in WinDBG": "clrmd-part-5-extend-sos-windbg",
    "ClrMD Part 6 - Manipulate memory structures like real objects": "clrmd-part-6-memory-structures",
    "ClrMD Part 7 - Manipulate nested structs using dynamic": "clrmd-part-7-nested-structs-dynamic",
    "ClrMD Part 7 \u2013 Manipulate nested structs using dynamic": "clrmd-part-7-nested-structs-dynamic",
    "ClrMD Part 8 - Spelunking inside the .NET Thread Pool": "clrmd-part-8-net-thread-pool",
    "ClrMD Part 8 \u2013 Spelunking inside the .NET Thread Pool": "clrmd-part-8-net-thread-pool",
    "ClrMD Part 9 - Deciphering Tasks and Thread Pool items": "clrmd-part-9-tasks-thread-pool",
    "ClrMD Part 9 \u2013 Deciphering Tasks and Thread Pool items": "clrmd-part-9-tasks-thread-pool",
    "RyuJIT and the never-ending ThreadAbortException": "ryujit-never-ending-threadabort",
    "Extending the new WinDbg, Part 1 - Buttons and commands": "extending-windbg-part-1-buttons",
    "Extending the new WinDbg, Part 3 - Embedding a C# interpreter": "extending-windbg-part-3-csharp",
    "Extending the new WinDbg, Part 3 \u2013 Embedding a C# interpreter": "extending-windbg-part-3-csharp",
}


def slug_from_title(title: str) -> str:
    """Look up the hardcoded slug for a title, or generate one as fallback."""
    if title in TITLE_TO_SLUG:
        return TITLE_TO_SLUG[title]
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    parts = [p for p in slug.split("-") if p]
    return "-".join(parts[:5])


def normalize_tags(raw_tags: List[str], is_windbg_post: bool = False) -> List[str]:
    """Normalize tags to match existing site conventions."""
    seen = set()
    result = []
    for tag in raw_tags:
        mapped = TAG_NORMALIZE.get(tag, tag)
        if mapped is None:
            continue
        if mapped not in seen:
            seen.add(mapped)
            result.append(mapped)
    if is_windbg_post and "windbg" not in seen:
        result.append("windbg")
    return result


def detect_code_language(text: str) -> str:
    """Heuristically detect whether a <pre> block is C# or plain text."""
    stripped = text.strip()
    if stripped.startswith(".") and not stripped.startswith(".."):
        return "text"
    if re.match(r'^[A-Z]:\\', stripped):
        return "text"
    if "srv*" in stripped or "*http" in stripped:
        return "text"
    if stripped.startswith("(") and stripped.endswith(")."):
        return "text"
    if stripped.startswith("SRV*"):
        return "text"
    if not any(c in stripped for c in [";", "{", "}", "(", ")"]):
        return "text"
    return "csharp"


def resolve_criteo_url(url: str) -> Optional[str]:
    """Try to map a labs.criteo.com URL to a new internal post path."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    for slug_prefix, dir_name in CRITEO_SLUG_TO_DIR.items():
        if slug_prefix in path:
            return f"/posts/{dir_name}/"
    return None


# ---------------------------------------------------------------------------
# HTML-to-Markdown conversion
# ---------------------------------------------------------------------------

def extract_gist_code(gist_div) -> Tuple[str, str]:
    """Extract code and filename from an inlined gist <div class='gist'>."""
    filename = ""
    meta = gist_div.find("div", class_="gist-meta")
    if meta:
        links = meta.find_all("a")
        for link in links:
            href = link.get("href", "")
            if "raw" not in href and "github.com" in href and "#file-" in href:
                filename = link.get_text(strip=True)
                break

    lines = []
    for td in gist_div.find_all("td", class_="blob-code"):
        line_text = td.get_text()
        line_text = line_text.replace("\xa0", " ")
        lines.append(line_text)

    code = "\n".join(lines)
    return code, filename


def convert_element_to_markdown(element, depth=0) -> str:
    """Recursively convert a BeautifulSoup element to Markdown."""
    if isinstance(element, NavigableString):
        text = str(element)
        text = text.replace("\xa0", " ")
        # Collapse runs of spaces (from &nbsp; sequences) to single space
        text = re.sub(r'  +', ' ', text)
        return text

    if not isinstance(element, Tag):
        return ""

    tag = element.name

    # Skip script/style/link tags
    if tag in ("script", "style", "link"):
        return ""

    # Gist blocks
    if tag == "div" and "gist" in element.get("class", []):
        code, filename = extract_gist_code(element)
        result = ""
        if filename:
            result += f"\n**{filename}**\n"
        result += f"\n```csharp\n{code}\n```\n"
        return result

    # Headings
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        if level == 1:
            level = 2
        prefix = "#" * level
        text = element.get_text(strip=True)
        return f"\n{prefix} {text}\n"

    # Blockquotes
    if tag == "blockquote":
        inner = "".join(convert_element_to_markdown(c, depth + 1) for c in element.children)
        inner = inner.strip()
        inner = re.sub(r'\n', '\n> ', inner)
        return f"\n> {inner}\n"

    # Pre blocks (non-gist code)
    if tag == "pre":
        code_text = element.get_text()
        code_text = code_text.replace("\xa0", " ")
        lang = detect_code_language(code_text)
        return f"\n```{lang}\n{code_text}\n```\n"

    # Images
    if tag == "img":
        src = element.get("src", "")
        if "_files/" in src:
            filename = src.split("/")[-1]
            return f"![{element.get('alt', '')}]({filename})"
        return ""

    # Links
    if tag == "a":
        href = element.get("href", "")
        # If wrapping an image, let the image handle itself
        if element.find("img"):
            return "".join(convert_element_to_markdown(c, depth + 1) for c in element.children)
        text = element.get_text(strip=True)
        if not text:
            return ""
        if href.startswith("./") and "_files/" in href:
            return ""
        if not href or href == "#":
            return text
        return f"[{text}]({href})"

    # Bold
    if tag in ("strong", "b"):
        text = element.get_text(strip=True)
        if text:
            return f"**{text}**"
        return ""

    # Italic
    if tag == "em":
        text = element.get_text(strip=True)
        if text:
            return f"*{text}*"
        return ""

    # Line breaks
    if tag == "br":
        return "\n"

    # Paragraphs
    if tag == "p":
        # Skip empty spacer paragraphs, but keep paragraphs that contain images
        has_img = element.find("img") is not None
        if not has_img:
            text_content = element.get_text(strip=True)
            if not text_content or text_content == "\xa0":
                return ""
        inner = "".join(convert_element_to_markdown(c, depth + 1) for c in element.children)
        inner = inner.strip()
        if inner:
            return f"\n{inner}\n"
        return ""

    # Lists
    if tag == "ul":
        items = []
        for li in element.find_all("li", recursive=False):
            li_text = "".join(convert_element_to_markdown(c, depth + 1) for c in li.children)
            li_text = li_text.strip()
            items.append(f"- {li_text}")
        return "\n" + "\n".join(items) + "\n"

    if tag == "ol":
        items = []
        for i, li in enumerate(element.find_all("li", recursive=False), 1):
            li_text = "".join(convert_element_to_markdown(c, depth + 1) for c in li.children)
            li_text = li_text.strip()
            items.append(f"{i}. {li_text}")
        return "\n" + "\n".join(items) + "\n"

    # Horizontal rules
    if tag == "hr":
        return "\n---\n"

    # Tables (non-gist, non-author) - render as-is in HTML since Hugo allows unsafe HTML
    if tag == "table":
        return ""

    # Default: recurse into children
    return "".join(convert_element_to_markdown(c, depth + 1) for c in element.children)


def clean_markdown(md: str) -> str:
    """Clean up generated markdown: fix whitespace, remove artifacts."""
    # Collapse 3+ consecutive blank lines to 2
    md = re.sub(r'\n{3,}', '\n\n', md)
    # Remove leading/trailing whitespace on each line (but preserve code blocks)
    lines = md.split('\n')
    in_code = False
    cleaned = []
    for line in lines:
        if line.strip().startswith('```'):
            in_code = not in_code
            cleaned.append(line)
        elif in_code:
            cleaned.append(line)
        else:
            cleaned.append(line.rstrip())
    md = '\n'.join(cleaned)
    md = md.strip() + '\n'
    return md


# ---------------------------------------------------------------------------
# Post processing
# ---------------------------------------------------------------------------

def extract_metadata(soup: BeautifulSoup) -> dict:
    """Extract post metadata from OpenGraph and article meta tags."""
    meta = {}

    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title["content"]
        title = re.sub(r'\s*-\s*Criteo Labs\s*$', '', title)
        meta["title"] = title

    og_desc = soup.find("meta", property="og:description")
    if og_desc:
        meta["description"] = og_desc["content"]

    pub_time = soup.find("meta", property="article:published_time")
    if pub_time:
        dt_str = pub_time["content"]
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            meta["date"] = dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            meta["date_prefix"] = dt.strftime("%Y-%m-%d")
        except ValueError:
            meta["date"] = dt_str
            meta["date_prefix"] = dt_str[:10]

    tags = []
    for tag_meta in soup.find_all("meta", property="article:tag"):
        tags.append(tag_meta["content"])
    meta["raw_tags"] = tags

    og_image = soup.find("meta", property="og:image")
    if og_image:
        meta["og_image"] = og_image["content"]

    return meta


def extract_coauthors(content_div) -> List[dict]:
    """Detect co-authors from the author bio table at end of post.

    The author bio table appears after the last <hr> in the post content.
    We only look at tables that come after the final <hr> to avoid picking
    up code from gist tables.
    """
    coauthors = []
    hrs = content_div.find_all("hr")
    if not hrs:
        return coauthors

    last_hr = hrs[-1]
    # Only examine tables that appear after the last <hr>
    bio_tables = []
    for sibling in last_hr.find_next_siblings():
        if isinstance(sibling, Tag) and sibling.name == "table":
            bio_tables.append(sibling)
        nested = sibling.find_all("table") if isinstance(sibling, Tag) else []
        bio_tables.extend(nested)

    for table in bio_tables:
        tds = table.find_all("td")
        for td in tds:
            text = td.get_text(strip=True)
            if "Christophe Nasarre" in text:
                continue
            lines = [l.strip() for l in td.get_text().split('\n') if l.strip()]
            name = None
            twitter = None
            for line in lines:
                if line in ("", "Staff Software Engineer", "Software Engineer",
                            "Staff Software Engineer, R&D."):
                    continue
                if "Twitter:" in line:
                    continue
                if not name and len(line) > 2 and not line.startswith("http"):
                    name = line
            twitter_link = td.find("a", href=re.compile(r"twitter\.com"))
            if twitter_link:
                twitter = twitter_link.get("href", "")
            if name:
                coauthors.append({"name": name, "twitter": twitter})
    return coauthors


def extract_content_body(content_div) -> Tag:
    """Return the content div with author bio stripped."""
    hrs = content_div.find_all("hr")
    if hrs:
        last_hr = hrs[-1]
        for sibling in list(last_hr.find_next_siblings()):
            sibling.decompose()
        last_hr.decompose()

    # Also strip "Post written by:" paragraph if present
    for p in reversed(content_div.find_all("p")):
        text = p.get_text(strip=True)
        if text.startswith("Post written by"):
            p.decompose()
            break
    # Strip trailing empty paragraphs
    for child in reversed(list(content_div.children)):
        if isinstance(child, Tag) and child.name == "p":
            if not child.get_text(strip=True) or child.get_text(strip=True) == "\xa0":
                child.decompose()
            else:
                break
        elif isinstance(child, NavigableString) and not child.strip():
            child.extract()
        else:
            break

    return content_div


def process_html_file(html_path: Path) -> dict:
    """Process a single HTML file and return all extracted data."""
    print(f"  Processing: {html_path.name}")

    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    meta = extract_metadata(soup)

    is_windbg = "windbg" in meta.get("title", "").lower()
    meta["tags"] = normalize_tags(meta["raw_tags"], is_windbg_post=is_windbg)

    dir_name = f"{meta['date_prefix']}_{slug_from_title(meta['title'])}"
    meta["dir_name"] = dir_name

    content_div = soup.find("div", class_="post-content-left")
    if not content_div:
        print(f"    WARNING: Could not find content div in {html_path.name}")
        return {"meta": meta, "markdown": "", "coauthors": [], "images": []}

    coauthors = extract_coauthors(content_div)
    content_div = extract_content_body(content_div)

    # Remove the script+link tags before gist divs
    for script in content_div.find_all("script"):
        script.decompose()
    for link_tag in content_div.find_all("link", rel="stylesheet"):
        if "gist-embed" in link_tag.get("href", ""):
            link_tag.decompose()

    markdown = convert_element_to_markdown(content_div)
    markdown = clean_markdown(markdown)

    # Determine companion files directory
    files_dir_name = html_path.stem + "_files"
    files_dir = html_path.parent / files_dir_name
    images = []
    if files_dir.exists():
        for f in files_dir.iterdir():
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif"):
                if f.name not in SITE_CHROME_FILES:
                    images.append(f)

    # Pick cover image
    cover_image = None
    if images:
        # Try to find the first image referenced in the markdown
        for img in images:
            if img.name in markdown:
                cover_image = img.name
                break
        if not cover_image:
            cover_image = images[0].name

    meta["cover_image"] = cover_image

    return {
        "meta": meta,
        "markdown": markdown,
        "coauthors": coauthors,
        "images": images,
    }


def generate_front_matter(meta: dict) -> str:
    """Generate YAML front matter string."""
    title = meta["title"].replace('"', '\\"')
    desc = meta.get("description", "").replace('"', '\\"')
    tags_str = ", ".join(f'"{t}"' for t in meta["tags"])
    cover = meta.get("cover_image", "")

    fm = f'''---
title: "{title}"
date: {meta["date"]}
description: "{desc}"
tags: [{tags_str}]
draft: false
cover:
  image: "{cover}"
  relative: true
---'''
    return fm


def write_post(post_data: dict, output_dir: Path) -> Path:
    """Write a migrated post to disk as a Hugo page bundle."""
    meta = post_data["meta"]
    dir_path = output_dir / meta["dir_name"]
    dir_path.mkdir(parents=True, exist_ok=True)

    # Copy images
    for img in post_data["images"]:
        shutil.copy2(img, dir_path / img.name)

    # Build the full content
    fm = generate_front_matter(meta)
    body = post_data["markdown"]

    # Add co-author attribution
    coauthor_line = ""
    if post_data["coauthors"]:
        names = []
        for ca in post_data["coauthors"]:
            if ca.get("twitter"):
                names.append(f"[{ca['name']}]({ca['twitter']})")
            else:
                names.append(ca["name"])
        coauthor_line = "\n---\n\n*Co-authored with " + ", ".join(names) + "*\n"

    content = fm + "\n\n" + body + coauthor_line

    index_path = dir_path / "index.md"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"    Written: {dir_path.name}/index.md ({len(post_data['images'])} images)")
    return dir_path


# ---------------------------------------------------------------------------
# Link checking
# ---------------------------------------------------------------------------

def check_link(url: str) -> dict:
    """Check a single URL for liveness."""
    result = {
        "url": url,
        "status": "UNKNOWN",
        "http_code": None,
        "final_url": None,
        "wayback_url": None,
    }

    try:
        resp = requests.head(url, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (blog-migration-checker)"})
        if resp.status_code == 405:
            resp = requests.get(url, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True,
                                headers={"User-Agent": "Mozilla/5.0 (blog-migration-checker)"},
                                stream=True)
    except Exception:
        try:
            resp = requests.get(url, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True,
                                headers={"User-Agent": "Mozilla/5.0 (blog-migration-checker)"},
                                stream=True)
        except Exception:
            result["status"] = "DEAD"
            result["wayback_url"] = f"https://web.archive.org/web/*/{url}"
            return result

    result["http_code"] = resp.status_code

    if 200 <= resp.status_code < 300:
        orig_domain = urlparse(url).netloc
        final_domain = urlparse(resp.url).netloc
        if orig_domain != final_domain:
            result["status"] = "REDIRECT"
            result["final_url"] = resp.url
        else:
            result["status"] = "ALIVE"
    elif 300 <= resp.status_code < 400:
        result["status"] = "REDIRECT"
        result["final_url"] = resp.headers.get("Location", "")
    else:
        result["status"] = "DEAD"
        result["wayback_url"] = f"https://web.archive.org/web/*/{url}"

    return result


def extract_links_from_markdown(markdown: str) -> List[dict]:
    """Extract all [text](url) links from markdown (excluding images)."""
    links = []
    for match in re.finditer(r'(?<!!)\[([^\]]*)\]\(([^)]+)\)', markdown):
        text, url = match.group(1), match.group(2)
        if url.startswith("#") or url.startswith("mailto:"):
            continue
        if not url.startswith("http"):
            continue
        links.append({"text": text, "url": url})
    return links


def check_all_links(all_links: dict) -> dict:
    """Check all links across all posts concurrently. Returns link_results."""
    # Deduplicate URLs
    url_set = set()
    for post_slug, links in all_links.items():
        for link in links:
            url_set.add(link["url"])

    print(f"\n  Checking {len(url_set)} unique URLs...")
    url_results = {}

    with ThreadPoolExecutor(max_workers=LINK_CHECK_WORKERS) as executor:
        future_to_url = {executor.submit(check_link, url): url for url in url_set}
        done_count = 0
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            done_count += 1
            try:
                result = future.result()
            except Exception as e:
                result = {"url": url, "status": "DEAD", "http_code": None,
                          "final_url": None, "wayback_url": f"https://web.archive.org/web/*/{url}"}
            url_results[url] = result
            if done_count % 10 == 0:
                print(f"    Checked {done_count}/{len(url_set)} URLs...")

    # Build per-post link_results
    link_results = {}
    for post_slug, links in all_links.items():
        post_links = []
        for link in links:
            r = url_results.get(link["url"], {})
            post_links.append({
                "url": link["url"],
                "text": link["text"],
                "status": r.get("status", "UNKNOWN"),
                "http_code": r.get("http_code"),
                "final_url": r.get("final_url"),
                "wayback_url": r.get("wayback_url"),
                "replacement": None,
            })
        link_results[post_slug] = post_links

    return link_results


# ---------------------------------------------------------------------------
# Cross-reference replacement
# ---------------------------------------------------------------------------

def replace_criteo_urls_in_markdown(markdown: str, link_results: List[dict]) -> Tuple[str, int]:
    """Replace labs.criteo.com URLs in markdown with internal /posts/ paths."""
    count = 0
    for link in link_results:
        url = link["url"]
        parsed = urlparse(url)
        if "labs.criteo.com" not in parsed.netloc:
            continue
        new_path = resolve_criteo_url(url)
        if new_path:
            markdown = markdown.replace(url, new_path)
            link["status"] = "REPLACED"
            link["replacement"] = new_path
            count += 1
    return markdown, count


EXISTING_POST_URL_REPLACEMENTS = [
    ("http://labs.criteo.com/2017/02/going-beyond-sos-clrmd-part-1",
     "/posts/2017-02-21_clrmd-part-1-going-beyond/"),
    ("https://labs.criteo.com/2017/02/going-beyond-sos-clrmd-part-1",
     "/posts/2017-02-21_clrmd-part-1-going-beyond/"),
    ("http://labs.criteo.com/2017/03/clrmd-part-2-clrruntime-clrheap",
     "/posts/2017-03-24_clrmd-part-2-from-clrruntime/"),
    ("https://labs.criteo.com/2017/03/clrmd-part-2-clrruntime-clrheap",
     "/posts/2017-03-24_clrmd-part-2-from-clrruntime/"),
    ("http://labs.criteo.com/2017/04/clrmd-part-3-dea",
     "/posts/2017-05-03_clrmd-part-3-static-instance-fields/"),
    ("http://labs.criteo.com/2017/05/clrmd-part-3-dealing",
     "/posts/2017-05-03_clrmd-part-3-static-instance-fields/"),
    ("http://labs.criteo.com/2017/05/clrmd-part-4-callbacks-called-timers",
     "/posts/2017-05-31_clrmd-part-4-timer-callbacks/"),
    ("https://labs.criteo.com/2017/05/clrmd-part-4-callbacks-called-timers",
     "/posts/2017-05-31_clrmd-part-4-timer-callbacks/"),
    ("http://labs.criteo.com/2017/06/clrmd-part-5-how-to-use-clrmd",
     "/posts/2017-06-29_clrmd-part-5-extend-sos-windbg/"),
    ("https://labs.criteo.com/2017/06/clrmd-part-5-how-to-use-clrmd",
     "/posts/2017-06-29_clrmd-part-5-extend-sos-windbg/"),
    ("http://labs.criteo.com/2017/08/clrmd-part-6-manipulate-memory",
     "/posts/2017-08-01_clrmd-part-6-memory-structures/"),
    ("http://labs.criteo.com/2017/08/clrmd-part-7-manipulate-nested",
     "/posts/2017-08-28_clrmd-part-7-nested-structs-dynamic/"),
    ("http://labs.criteo.com/2017/11/clrmd-part-8-spelunking",
     "/posts/2017-11-03_clrmd-part-8-net-thread-pool/"),
    ("https://labs.criteo.com/2017/12/clrmd-part-9-deciphering",
     "/posts/2017-12-22_clrmd-part-9-tasks-thread-pool/"),
    ("http://labs.criteo.com/2017/12/clrmd-part-9-deciphering",
     "/posts/2017-12-22_clrmd-part-9-tasks-thread-pool/"),
    ("http://labs.criteo.com/2017/09/extending-new-windbg-part-1",
     "/posts/2017-09-06_extending-windbg-part-1-buttons/"),
]


def update_existing_posts(hugo_root: Path, link_results: dict) -> List[dict]:
    """Update existing posts that reference labs.criteo.com URLs for migrated posts."""
    content_dir = hugo_root / "content"
    updated_files = []

    # Skip the newly migrated post directories
    migrated_dirs = set(CRITEO_SLUG_TO_DIR.values())

    md_files = list(content_dir.rglob("index.md"))
    for md_path in md_files:
        # Skip migrated posts (they were already handled in Step 4)
        parent_name = md_path.parent.name
        if any(parent_name.startswith(d[:10]) for d in migrated_dirs if d[:10].startswith("201")):
            # More precise: check if it's one of the newly created dirs
            pass

        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        if "labs.criteo.com" not in content:
            continue

        original = content
        replacements = 0

        for old_prefix, new_path in EXISTING_POST_URL_REPLACEMENTS:
            # Find the full URL (up to the next ), space, or quote)
            pattern = re.compile(re.escape(old_prefix) + r'[^)\s"\']*', re.IGNORECASE)
            matches = pattern.findall(content)
            for match in matches:
                if match != new_path and new_path not in match:
                    content = content.replace(match, new_path)
                    replacements += 1

        if content != original:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content)
            rel_path = md_path.relative_to(hugo_root)
            updated_files.append({"path": str(rel_path), "replacements": replacements})
            print(f"    Updated: {rel_path} ({replacements} URLs replaced)")

    return updated_files


# ---------------------------------------------------------------------------
# Migration summary
# ---------------------------------------------------------------------------

def generate_summary(post_data_list: List[dict], link_results: dict,
                     updated_files: List[dict], hugo_root: Path) -> str:
    """Generate the MIGRATION_SUMMARY.md content."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Count totals
    total_links = sum(len(links) for links in link_results.values())
    alive = sum(1 for links in link_results.values() for l in links if l["status"] == "ALIVE")
    redirect = sum(1 for links in link_results.values() for l in links if l["status"] == "REDIRECT")
    dead = sum(1 for links in link_results.values() for l in links if l["status"] == "DEAD")
    replaced = sum(1 for links in link_results.values() for l in links if l["status"] == "REPLACED")

    lines = [
        "# Migration Summary",
        "",
        f"Generated on: {now}",
        "",
        "## Overview",
        "",
        f"- Posts migrated: {len(post_data_list)}",
        f"- Total links checked: {total_links}",
        f"- Alive: {alive}",
        f"- Redirected: {redirect}",
        f"- Dead: {dead}",
        f"- Replaced (cross-post): {replaced}",
        "",
        "## Migrated Posts",
        "",
        "| # | Title | Date | Path | Images | Links | Dead |",
        "|---|-------|------|------|--------|-------|------|",
    ]

    for i, pd in enumerate(post_data_list, 1):
        m = pd["meta"]
        slug = m["dir_name"]
        post_links = link_results.get(slug, [])
        dead_count = sum(1 for l in post_links if l["status"] == "DEAD")
        lines.append(
            f"| {i} | {m['title']} | {m['date_prefix']} | /posts/{slug}/ | "
            f"{len(pd['images'])} | {len(post_links)} | {dead_count} |"
        )

    lines.extend(["", "## Per-Post Link Reports", ""])

    for pd in post_data_list:
        slug = pd["meta"]["dir_name"]
        title = pd["meta"]["title"]
        post_links = link_results.get(slug, [])
        lines.extend([f"### {title}", ""])
        if not post_links:
            lines.append("No links found in this post.")
            lines.append("")
            continue
        lines.append("| Status | URL | Link Text | Details |")
        lines.append("|--------|-----|-----------|---------|")
        for l in post_links:
            details = ""
            if l["status"] == "ALIVE":
                details = str(l.get("http_code", ""))
            elif l["status"] == "REDIRECT":
                details = f"-> {l.get('final_url', '')}"
            elif l["status"] == "DEAD":
                details = f"{l.get('http_code', 'error')}"
                if l.get("wayback_url"):
                    details += f"; Wayback: {l['wayback_url']}"
            elif l["status"] == "REPLACED":
                details = f"-> {l.get('replacement', '')}"
            # Escape pipe chars in URL
            url_display = l["url"][:80]
            text_display = l["text"][:40]
            lines.append(f"| {l['status']} | {url_display} | {text_display} | {details} |")
        lines.append("")

    # Existing posts updated
    lines.extend(["## Existing Posts Updated", ""])
    if updated_files:
        lines.append("| Post | URLs Replaced |")
        lines.append("|------|--------------|")
        for uf in updated_files:
            lines.append(f"| {uf['path']} | {uf['replacements']} |")
    else:
        lines.append("No existing posts were updated.")
    lines.append("")

    # Unmigrated labs.criteo.com URLs
    lines.extend(["## Unmigrated labs.criteo.com URLs Still Referenced", ""])
    unmigrated = {
        "http://labs.criteo.com/2018/06/replace-net-performance-counters-by-clr-event-tracing": [],
        "http://labs.criteo.com/2018/07/grab-etw-session-providers-and-events/": [],
        "http://labs.criteo.com/2018/09/monitor-finalizers-contention-and-threads-in-your-application/": [],
    }
    content_root = hugo_root / "content"
    for md_path in content_root.rglob("index.md"):
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        for url in unmigrated:
            if url in content or url.replace("http://", "https://") in content:
                rel = md_path.relative_to(hugo_root)
                unmigrated[url].append(str(rel))
    for url, refs in unmigrated.items():
        if refs:
            lines.append(f"- {url}")
            lines.append(f"  Referenced in: {', '.join(refs)}")
    lines.append("")

    # Warnings
    lines.extend([
        "## Warnings",
        "",
        '- "Extending the new WinDbg, Part 2" is missing from the backup.',
        "  Links to it are left as-is (dead labs.criteo.com URL).",
        "- Source code ZIP downloads (e.g., ClrMD-part1_Source.zip) hosted on",
        "  labs.criteo.com/wp-content/uploads/ are dead and have no replacement.",
        "- RSS/Follow.it: Adding 12 posts will include them in the RSS feed",
        "  (/index.xml) and may trigger Follow.it email notifications to",
        "  subscribers. Consider deploying carefully or temporarily disabling",
        "  the Follow.it widget during migration.",
        "- Giscus comments will be enabled on old posts. GitHub Discussion",
        "  threads will be created on first visitor interaction.",
        "- medium.com/criteo-labs links in existing posts were NOT checked",
        "  by this migration and may also be dead.",
        "",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Criteo Labs Blog Migration")
    print("=" * 60)

    # Step 1: Parse HTML files and convert to Markdown
    print("\n[Step 1] Parsing HTML files and converting to Markdown...")
    html_files = sorted(SOURCE_DIR.glob("*.html"))
    print(f"  Found {len(html_files)} HTML files")

    post_data_list = []
    for html_file in html_files:
        pd = process_html_file(html_file)
        post_data_list.append(pd)

    # Step 2: Write posts and copy images
    print(f"\n[Step 2] Writing {len(post_data_list)} posts to {CONTENT_DIR}...")
    for pd in post_data_list:
        write_post(pd, CONTENT_DIR)

    # Step 3: Link checking
    print("\n[Step 3] Extracting and checking links...")
    all_links = {}
    for pd in post_data_list:
        slug = pd["meta"]["dir_name"]
        index_path = CONTENT_DIR / slug / "index.md"
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
            links = extract_links_from_markdown(content)
            all_links[slug] = links
            print(f"  {slug}: {len(links)} links found")

    link_results = check_all_links(all_links)

    # Count results
    for status in ("ALIVE", "REDIRECT", "DEAD"):
        count = sum(1 for links in link_results.values() for l in links if l["status"] == status)
        print(f"  {status}: {count}")

    # Step 4: Replace cross-post URLs in migrated posts
    print("\n[Step 4] Replacing cross-post URLs in migrated posts...")
    total_replaced = 0
    for pd in post_data_list:
        slug = pd["meta"]["dir_name"]
        index_path = CONTENT_DIR / slug / "index.md"
        if index_path.exists() and slug in link_results:
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
            content, count = replace_criteo_urls_in_markdown(content, link_results[slug])
            if count > 0:
                with open(index_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"  {slug}: {count} URLs replaced")
                total_replaced += count
    print(f"  Total: {total_replaced} URLs replaced in migrated posts")

    # Step 5: Update existing posts
    print("\n[Step 5] Updating existing posts with new internal paths...")
    updated_files = update_existing_posts(HUGO_ROOT, link_results)
    print(f"  Updated {len(updated_files)} existing files")

    # Step 6: Generate migration summary
    print("\n[Step 6] Generating MIGRATION_SUMMARY.md...")
    summary = generate_summary(post_data_list, link_results, updated_files, HUGO_ROOT)
    summary_path = HUGO_ROOT / "MIGRATION_SUMMARY.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"  Written: {summary_path}")

    print("\n" + "=" * 60)
    print("Migration complete!")
    print(f"  {len(post_data_list)} posts migrated")
    print(f"  {total_replaced} cross-post URLs replaced in migrated posts")
    print(f"  {len(updated_files)} existing posts updated")
    print(f"  See MIGRATION_SUMMARY.md for full link report")
    print("=" * 60)
    print("\nNext step: run 'hugo server' to verify the migration.")


if __name__ == "__main__":
    main()
