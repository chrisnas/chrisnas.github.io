"""
Migrate 3 Medium ETW/TraceEvent blog posts to the Hugo/PaperMod GitHub Pages site.

Source: C:\Personel\Blog\Criteo (saved Medium HTML files)
Target: C:\Personel\Blog\GithubPages\chrisnas.github.io

Handles:
- Medium HTML parsing and metadata extraction
- Gist extraction from iframe-embedded HTML files
- Image filtering (skip Medium UI chrome: avatars, promo banners)
- HTML-to-Markdown conversion
- Dead link detection with concurrent HTTP checking
- Cross-reference replacement (labs.criteo.com -> /posts/ paths)
- Update of existing posts (Medium URLs -> new internal paths)
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
    print("Missing dependencies. Install with: py -m pip install beautifulsoup4 requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_DIR = Path(r"C:\Personel\Blog\Criteo")
HUGO_ROOT = Path(r"C:\Personel\Blog\GithubPages\chrisnas.github.io")
CONTENT_DIR = HUGO_ROOT / "content" / "posts"
SCRIPT_DIR = HUGO_ROOT / "CriteoMigration"

LINK_CHECK_TIMEOUT = 10
LINK_CHECK_WORKERS = 10

# ---------------------------------------------------------------------------
# Post definitions: hardcoded metadata for each Medium post
# ---------------------------------------------------------------------------

POST_DEFS = [
    {
        "html_prefix": "Replace .NET performance counters",
        "title": "Replace .NET performance counters by CLR event tracing",
        "description": "This post of our new series shows why performance counters might not be the best solution to monitor your .NET application.",
        "date": "2018-06-19T00:00:00.000Z",
        "date_prefix": "2018-06-19",
        "dir_name": "2018-06-19_replace-net-performance-counters",
        "tags": [".NET", "ETW", "TraceEvent", "Performance", "CLR"],
        "cover_override": "0_TxC5sfAh5Mfguhxn.png",
    },
    {
        "html_prefix": "Grab ETW Session",
        "title": "Grab ETW Session, Providers and Events",
        "description": "This post of the series shows how to easily listen to CLR events with the TraceEvent package.",
        "date": "2018-07-26T00:00:00.000Z",
        "date_prefix": "2018-07-26",
        "dir_name": "2018-07-26_grab-etw-session-providers",
        "tags": [".NET", "ETW", "TraceEvent", "Performance", "CLR"],
    },
    {
        "html_prefix": "Monitor Finalizers",
        "title": "Monitor Finalizers, contention and threads in your application",
        "description": "This post of the series details more complicated CLR events related to finalizers and threading.",
        "date": "2018-09-28T00:00:00.000Z",
        "date_prefix": "2018-09-28",
        "dir_name": "2018-09-28_monitor-finalizers-contention-threads",
        "tags": [".NET", "ETW", "TraceEvent", "Performance", "CLR", "Threading"],
    },
]

# Images that belong to Medium UI, not post content
MEDIUM_CHROME_IMAGES = {
    "1_WGftjNnfLwlWCeBno0xQCg.png",      # Criteo Tech avatar
    "1_WGftjNnfLwlWCeBno0xQCg(1).png",
    "1_WGftjNnfLwlWCeBno0xQCg(2).png",
}

MEDIUM_CHROME_TEXTS = {"Listen", "Share", "More"}

# ---------------------------------------------------------------------------
# Cross-reference mappings
# ---------------------------------------------------------------------------

# Maps labs.criteo.com URL prefixes to new Hugo post paths.
# Includes all previously migrated posts AND the 3 new ones.
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
    # The 3 new ETW posts
    "2018/06/replace-net-performance-counters": "2018-06-19_replace-net-performance-counters",
    "2018/07/grab-etw-session-providers": "2018-07-26_grab-etw-session-providers",
    "2018/09/monitor-finalizers-contention": "2018-09-28_monitor-finalizers-contention-threads",
}

# Medium URLs -> new internal paths (for updating existing posts)
MEDIUM_URL_REPLACEMENTS = [
    ("https://medium.com/p/4ebb9485f34d",
     "/posts/2018-06-19_replace-net-performance-counters/"),
    ("https://medium.com/p/516ee5396a86",
     "/posts/2018-07-26_grab-etw-session-providers/"),
    ("https://medium.com/criteo-engineering/monitor-finalizers-contention-and-threads-in-your-application-91b3db798958",
     "/posts/2018-09-28_monitor-finalizers-contention-threads/"),
]

# labs.criteo.com URL prefixes for these 3 ETW posts (both http/https)
CRITEO_ETW_URL_REPLACEMENTS = [
    ("http://labs.criteo.com/2018/06/replace-net-performance-counters-by-clr-event-tracing",
     "/posts/2018-06-19_replace-net-performance-counters/"),
    ("https://labs.criteo.com/2018/06/replace-net-performance-counters-by-clr-event-tracing",
     "/posts/2018-06-19_replace-net-performance-counters/"),
    ("http://labs.criteo.com/2018/07/grab-etw-session-providers-and-events",
     "/posts/2018-07-26_grab-etw-session-providers/"),
    ("https://labs.criteo.com/2018/07/grab-etw-session-providers-and-events",
     "/posts/2018-07-26_grab-etw-session-providers/"),
    ("http://labs.criteo.com/2018/09/monitor-finalizers-contention-and-threads-in-your-application",
     "/posts/2018-09-28_monitor-finalizers-contention-threads/"),
    ("https://labs.criteo.com/2018/09/monitor-finalizers-contention-and-threads-in-your-application",
     "/posts/2018-09-28_monitor-finalizers-contention-threads/"),
]


# ---------------------------------------------------------------------------
# Gist extraction
# ---------------------------------------------------------------------------

def extract_gist_code(gist_div) -> Tuple[str, str]:
    """Extract code and filename from a gist <div class='gist'>."""
    filename = ""
    meta = gist_div.find("div", class_="gist-meta")
    if meta:
        for link in meta.find_all("a"):
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


def extract_gist_from_iframe(iframe_path: Path) -> Tuple[str, str]:
    """Open a saved iframe HTML file and extract the gist code from it."""
    if not iframe_path.exists():
        return "", ""
    with open(iframe_path, "r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    gist_div = soup.find("div", class_="gist")
    if not gist_div:
        return "", ""
    return extract_gist_code(gist_div)


# ---------------------------------------------------------------------------
# HTML-to-Markdown conversion
# ---------------------------------------------------------------------------

def convert_element_to_markdown(element, files_dir: Path, depth: int = 0) -> str:
    """Recursively convert a BeautifulSoup element to Markdown."""
    if isinstance(element, NavigableString):
        text = str(element)
        text = text.replace("\xa0", " ")
        text = re.sub(r'  +', ' ', text)
        return text

    if not isinstance(element, Tag):
        return ""

    tag = element.name

    if tag in ("script", "style", "link", "button", "source"):
        return ""

    # Figure: either an image or an iframe (gist)
    if tag == "figure":
        iframe = element.find("iframe")
        if iframe:
            src = iframe.get("src", "")
            iframe_basename = src.split("/")[-1] if "/" in src else src
            iframe_path = files_dir / iframe_basename
            code, filename = extract_gist_from_iframe(iframe_path)
            if code:
                result = ""
                if filename:
                    result += f"\n**{filename}**\n"
                result += f"\n```csharp\n{code}\n```\n"
                return result
            return ""

        img = element.find("img")
        if img:
            src = img.get("src", "")
            if "_files/" in src:
                fname = src.split("/")[-1]
                if fname in MEDIUM_CHROME_IMAGES:
                    return ""
                alt = img.get("alt", "")
                caption = element.find("figcaption")
                cap_text = caption.get_text(strip=True) if caption else ""
                if cap_text:
                    return f"\n![{alt}]({fname})\n*{cap_text}*\n"
                return f"\n![{alt}]({fname})\n"
        return ""

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
        inner = "".join(convert_element_to_markdown(c, files_dir, depth + 1)
                        for c in element.children)
        inner = inner.strip()
        inner = re.sub(r'\n', '\n> ', inner)
        return f"\n> {inner}\n"

    # Pre blocks
    if tag == "pre":
        code_text = element.get_text()
        code_text = code_text.replace("\xa0", " ")
        return f"\n```csharp\n{code_text}\n```\n"

    # Images (standalone, outside figure)
    if tag == "img":
        src = element.get("src", "")
        if "_files/" in src:
            fname = src.split("/")[-1]
            if fname in MEDIUM_CHROME_IMAGES:
                return ""
            return f"![{element.get('alt', '')}]({fname})"
        return ""

    # Links
    if tag == "a":
        href = element.get("href", "")
        # Skip Medium promo links
        if any(x in href for x in ["medium.com/plans", "medium.com/write",
                                    "medium.com/@", "events.zoom.us"]):
            return ""
        if element.find("img"):
            return "".join(convert_element_to_markdown(c, files_dir, depth + 1)
                          for c in element.children)
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
        if text == "Post written by:":
            return ""
        if text:
            return f"**{text}**"
        return ""

    # Italic
    if tag in ("em", "i"):
        text = element.get_text(strip=True)
        if text:
            return f"*{text}*"
        return ""

    # Line breaks
    if tag == "br":
        return "\n"

    # Paragraphs
    if tag == "p":
        text_content = element.get_text(strip=True)
        # Skip Medium chrome paragraphs
        if text_content in MEDIUM_CHROME_TEXTS:
            return ""
        # Skip pure clap-count paragraphs (single digit)
        if text_content.isdigit():
            return ""
        # Skip Medium reading-time lines like "5 min read·Jun 19, 2018"
        if re.match(r'^\d+ min read', text_content):
            return ""
        has_img = element.find("img") is not None
        if not has_img:
            if not text_content or text_content == "\xa0":
                return ""
        inner = "".join(convert_element_to_markdown(c, files_dir, depth + 1)
                        for c in element.children)
        inner = inner.strip()
        if inner:
            return f"\n{inner}\n"
        return ""

    # Lists
    if tag == "ul":
        items = []
        for li in element.find_all("li", recursive=False):
            li_text = "".join(convert_element_to_markdown(c, files_dir, depth + 1)
                              for c in li.children)
            li_text = li_text.strip()
            items.append(f"- {li_text}")
        return "\n" + "\n".join(items) + "\n"

    if tag == "ol":
        items = []
        for i, li in enumerate(element.find_all("li", recursive=False), 1):
            li_text = "".join(convert_element_to_markdown(c, files_dir, depth + 1)
                              for c in li.children)
            li_text = li_text.strip()
            items.append(f"{i}. {li_text}")
        return "\n" + "\n".join(items) + "\n"

    # Horizontal rules
    if tag == "hr":
        return "\n---\n"

    # Tables
    if tag == "table":
        return ""

    # Default: recurse into children
    return "".join(convert_element_to_markdown(c, files_dir, depth + 1)
                   for c in element.children)


def clean_markdown(md: str) -> str:
    """Clean up generated markdown: fix whitespace, remove artifacts."""
    # Remove Medium reading-time lines like "5 min read·Jun 19, 2018"
    md = re.sub(r'(?:^|\n)\d+ min read[^\n]*\n', '\n', md)
    md = re.sub(r'\n{3,}', '\n\n', md)
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

def find_html_file(prefix: str) -> Optional[Path]:
    """Find the HTML file whose name starts with the given prefix."""
    for f in SOURCE_DIR.glob("*.html"):
        if f.name.startswith(prefix):
            return f
    return None


def get_files_dir(html_path: Path) -> Path:
    """Return the companion _files directory for a given HTML file."""
    return html_path.parent / (html_path.stem + "_files")


def is_author_section(element) -> bool:
    """Detect whether an element is part of the post-content author bio."""
    if not isinstance(element, Tag):
        return False
    text = element.get_text(strip=True)
    if text.startswith("Post written by"):
        return True
    if text.startswith("Originally published at"):
        return True
    if text.startswith("Christophe Nasarre"):
        return True
    if text.startswith("Kevin Gosse"):
        return True
    if text.startswith("Staff Software Engineer"):
        return True
    if re.match(r'^Twitter:', text):
        return True
    return False


def is_author_image(element) -> bool:
    """Detect whether a figure contains an author bio image."""
    if not isinstance(element, Tag) or element.name != "figure":
        return False
    img = element.find("img")
    if not img:
        return False
    src = img.get("src", "")
    fname = src.split("/")[-1] if "/" in src else src
    # Author bio images are known filenames
    author_imgs = {
        "0_23V_Kuttt0zDv8Pr.png", "0_JzZOatnlgobJkMX5.jpg",
        "0_TgADqB2Koeos-6IK.png", "0_TpnFCmvCNWr452ct.jpg",
    }
    return fname in author_imgs or fname in MEDIUM_CHROME_IMAGES


def strip_author_and_footer(article) -> None:
    """Remove author bio and 'Originally published' footer from article in-place."""
    all_elements = article.find_all(['p', 'figure'])
    in_author_section = False
    for el in all_elements:
        text = el.get_text(strip=True)
        if text.startswith("Post written by"):
            in_author_section = True
        if text.startswith("Originally published at") or text.startswith("Originally published at"):
            el.decompose()
            continue
        if in_author_section:
            el.decompose()
            continue
        if is_author_image(el):
            el.decompose()


def process_medium_html(post_def: dict) -> dict:
    """Process a single Medium HTML file and return all extracted data."""
    html_path = find_html_file(post_def["html_prefix"])
    if not html_path:
        print(f"  ERROR: Could not find HTML file for '{post_def['html_prefix']}'")
        return {"meta": post_def, "markdown": "", "images": [], "content_images": set()}

    print(f"  Processing: {html_path.name}")
    files_dir = get_files_dir(html_path)

    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    if not article:
        print(f"    WARNING: No <article> tag found")
        return {"meta": post_def, "markdown": "", "images": [], "content_images": set()}

    strip_author_and_footer(article)

    # Remove the h1 title (already in front matter)
    h1 = article.find("h1")
    if h1:
        h1.decompose()

    # Remove the subtitle h2 (same as description, redundant)
    first_h2 = article.find("h2")
    if first_h2:
        h2_text = first_h2.get_text(strip=True)
        desc = post_def.get("description", "")
        if desc and (h2_text.startswith(desc[:40]) or desc.startswith(h2_text[:40])):
            first_h2.decompose()

    markdown = convert_element_to_markdown(article, files_dir)
    markdown = clean_markdown(markdown)

    # Collect images referenced in the markdown
    content_images = set(re.findall(r'!\[[^\]]*\]\(([^)]+)\)', markdown))

    # Gather all image files from _files dir
    images = []
    if files_dir.exists():
        for f in files_dir.iterdir():
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                if f.name in MEDIUM_CHROME_IMAGES:
                    continue
                if f.name in content_images:
                    images.append(f)

    # Pick cover image from post definition override, or og:image, or first content image
    cover_image = post_def.get("cover_override", None)
    if not cover_image:
        og_image_tag = soup.find("meta", attrs={"property": "og:image"})
        if og_image_tag:
            og_url = og_image_tag.get("content", "")
            og_basename = og_url.split("/")[-1]
            og_local = og_basename.replace("*", "_")
            if any(img.name == og_local for img in images):
                cover_image = og_local
    if not cover_image and images:
        for img in images:
            if img.name in content_images:
                cover_image = img.name
                break
    if not cover_image and images:
        cover_image = images[0].name

    post_def["cover_image"] = cover_image

    return {
        "meta": post_def,
        "markdown": markdown,
        "images": images,
        "content_images": content_images,
    }


# ---------------------------------------------------------------------------
# Front matter & writing
# ---------------------------------------------------------------------------

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

    for img in post_data["images"]:
        shutil.copy2(img, dir_path / img.name)

    fm = generate_front_matter(meta)
    body = post_data["markdown"]

    # All 3 posts are co-authored with Kevin Gosse
    coauthor_line = "\n---\n\n*Co-authored with [Kevin Gosse](https://twitter.com/kookiz)*\n"
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
    """Check all links across all posts concurrently."""
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
            except Exception:
                result = {"url": url, "status": "DEAD", "http_code": None,
                          "final_url": None,
                          "wayback_url": f"https://web.archive.org/web/*/{url}"}
            url_results[url] = result
            if done_count % 5 == 0:
                print(f"    Checked {done_count}/{len(url_set)} URLs...")

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

def resolve_criteo_url(url: str) -> Optional[str]:
    """Try to map a labs.criteo.com URL to a new internal post path."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    for slug_prefix, dir_name in CRITEO_SLUG_TO_DIR.items():
        if slug_prefix in path:
            return f"/posts/{dir_name}/"
    return None


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
    # Fix any double trailing slashes from replacement
    markdown = re.sub(r'(/posts/[^)]+?)//', r'\1/', markdown)
    return markdown, count


def update_existing_posts(hugo_root: Path) -> List[dict]:
    """Update existing posts: replace Medium and labs.criteo.com ETW URLs with new internal paths."""
    content_dir = hugo_root / "content"
    updated_files = []

    new_dirs = {pd["dir_name"] for pd in POST_DEFS}
    all_replacements = MEDIUM_URL_REPLACEMENTS + CRITEO_ETW_URL_REPLACEMENTS

    md_files = list(content_dir.rglob("index.md"))
    for md_path in md_files:
        if md_path.parent.name in new_dirs:
            continue

        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        original = content
        count = 0

        for old_prefix, new_path in all_replacements:
            # Match the prefix and consume the rest of the URL up to the next delimiter
            pattern = re.compile(re.escape(old_prefix) + r'[^)\s"\']*', re.IGNORECASE)
            matches = pattern.findall(content)
            for match in matches:
                if match != new_path and new_path not in match:
                    content = content.replace(match, new_path)
                    count += 1

        if content != original:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content)
            rel_path = md_path.relative_to(hugo_root)
            updated_files.append({"path": str(rel_path), "replacements": count})
            print(f"    Updated: {rel_path} ({count} URLs replaced)")

    return updated_files


# ---------------------------------------------------------------------------
# Migration summary
# ---------------------------------------------------------------------------

def generate_summary(post_data_list: List[dict], link_results: dict,
                     updated_files: List[dict]) -> str:
    """Generate the MediumMigration.md content."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_links = sum(len(links) for links in link_results.values())
    alive = sum(1 for links in link_results.values() for l in links if l["status"] == "ALIVE")
    redirect = sum(1 for links in link_results.values() for l in links if l["status"] == "REDIRECT")
    dead = sum(1 for links in link_results.values() for l in links if l["status"] == "DEAD")
    replaced = sum(1 for links in link_results.values() for l in links if l["status"] == "REPLACED")

    lines = [
        "# Medium Posts Migration Summary",
        "",
        f"Generated on: {now}",
        "",
        "## Overview",
        "",
        "Source: 3 Medium ETW/TraceEvent posts saved as HTML",
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
            url_display = l["url"][:80]
            text_display = l["text"][:40]
            lines.append(f"| {l['status']} | {url_display} | {text_display} | {details} |")
        lines.append("")

    lines.extend(["## Existing Posts Updated (Medium URLs -> Internal Paths)", ""])
    if updated_files:
        lines.append("| Post | URLs Replaced |")
        lines.append("|------|--------------|")
        for uf in updated_files:
            lines.append(f"| {uf['path']} | {uf['replacements']} |")
    else:
        lines.append("No existing posts were updated.")
    lines.append("")

    lines.extend([
        "## Notes",
        "",
        "- All 3 posts are co-authored with Kevin Gosse.",
        "- Tags were manually assigned (not available in Medium metadata).",
        "- Dates come from the 'Originally published at' footer (original Criteo Labs dates),",
        "  not from Medium's article:published_time (which reflects the Medium republication date).",
        "- Giscus comments will be enabled on these posts. GitHub Discussion",
        "  threads will be created on first visitor interaction.",
        "",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Medium ETW/TraceEvent Posts Migration")
    print("=" * 60)

    # Step 1: Parse HTML files and convert to Markdown
    print("\n[Step 1] Parsing Medium HTML files and converting to Markdown...")
    post_data_list = []
    for post_def in POST_DEFS:
        pd = process_medium_html(post_def)
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

    for status in ("ALIVE", "REDIRECT", "DEAD"):
        count = sum(1 for links in link_results.values()
                    for l in links if l["status"] == status)
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

    # Step 5: Update existing posts (Medium URLs -> internal paths)
    print("\n[Step 5] Updating existing posts (Medium URLs -> internal paths)...")
    updated_files = update_existing_posts(HUGO_ROOT)
    print(f"  Updated {len(updated_files)} existing files")

    # Step 6: Generate migration summary
    print("\n[Step 6] Generating MediumMigration.md...")
    summary = generate_summary(post_data_list, link_results, updated_files)
    summary_path = SCRIPT_DIR / "MediumMigration.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"  Written: {summary_path}")

    print("\n" + "=" * 60)
    print("Migration complete!")
    print(f"  {len(post_data_list)} posts migrated")
    print(f"  {total_replaced} cross-post URLs replaced in migrated posts")
    print(f"  {len(updated_files)} existing posts updated")
    print(f"  See CriteoMigration/MediumMigration.md for full report")
    print("=" * 60)
    print("\nNext step: run 'hugo server' to verify the migration.")


if __name__ == "__main__":
    main()
