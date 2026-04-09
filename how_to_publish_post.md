# How to Publish a New Blog Post

This site is built with [Hugo](https://gohugo.io/) using the [PaperMod](https://github.com/adityatelange/hugo-PaperMod) theme and automatically deployed to GitHub Pages.

## 1. Create the Post Folder

Create a new directory under `content/posts/` following this naming convention:

```
content/posts/YYYY-MM-DD_short-slug/index.md
```

For example: `content/posts/2026-04-09_my-new-post/index.md`

Place any images or assets for the post in the same folder alongside `index.md`.

## 2. Add YAML Front Matter

Your `index.md` must start with YAML front matter (`---` delimiters). Here is the template used by existing posts:

```yaml
---
title: "Your Post Title Here"
date: 2026-04-09T10:00:00.000Z
description: "A short summary for SEO and previews"
tags: ["tag1", "tag2"]
draft: false
cover:
  image: "your-cover-image.png"
  relative: true
---
```

| Field         | Description                                                        |
| ------------- | ------------------------------------------------------------------ |
| `title`       | The displayed post title                                           |
| `date`        | ISO datetime; controls post ordering                               |
| `description` | Short summary shown in listings and used for SEO                   |
| `tags`        | Array of tag strings                                               |
| `draft`       | Set to `false` when ready to publish; `true` keeps it hidden       |
| `cover.image` | Filename of the featured image (must be in the same folder)        |
| `cover.relative` | Must be `true` so Hugo resolves the image path relative to the post |

> **Note:** The default archetype at `archetypes/default.md` uses TOML (`+++`) delimiters, but all existing posts use YAML (`---`). If you scaffold a post with `hugo new`, convert the front matter to YAML to stay consistent — or simply copy front matter from an existing post.

## 3. Write the Post Content

Write the post body in Markdown after the closing `---`. Images placed in the post folder can be referenced with relative paths:

```markdown
![Alt text](my-image.png)
```

## 4. Preview Locally

Run the Hugo development server to check the result before publishing:

```bash
hugo server -D
```

The `-D` flag includes draft posts. Once you are happy with the result, make sure `draft` is set to `false` in the front matter.

## 5. Commit and Push to `main`

```bash
git add content/posts/YYYY-MM-DD_short-slug/
git commit -m "Add new blog post: Your Post Title"
git push origin main
```

## 6. Automatic Deployment

The GitHub Actions workflow at `.github/workflows/hugo.yml` triggers on every push to `main`. It:

1. Checks out the repo including the PaperMod theme submodule.
2. Builds the site with `hugo --gc --minify`.
3. Deploys the generated `public/` folder to GitHub Pages.

Posts with `draft: true` are **excluded** from the production build and will not appear on the live site.

## Working with Drafts

There is no separate drafts folder. To keep a post as a draft, simply set `draft: true` in its front matter. Draft posts:

- **Are visible** when running `hugo server -D` locally.
- **Are excluded** from the production build on GitHub Pages.

When ready to publish, change `draft` to `false`, commit, and push.

## Prerequisites

- [Hugo Extended](https://gohugo.io/installation/) (the CI uses v0.160.0)
- Git submodules must be initialized for the theme:

```bash
git submodule update --init --recursive
```
