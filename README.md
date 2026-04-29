# maxyaport.com

Astro site for `maxyaport.com`, with Sanity as the source of truth for posts.

## Commands

```sh
npm install
npm run dev
npm run studio
npm run build
```

## Posts

Run `npm run studio`, then open `http://localhost:3333` to write and edit posts in Sanity Studio.

Posts are Sanity documents with rich text, image blocks, and image carousel blocks. Astro builds writing pages from Sanity at `/writing/<slug>/`.

The original Markdown posts were migrated into Sanity and archived under `archive/markdown-posts/` for reference only. They are not used by the live site.

To re-import the archived Markdown posts into Sanity:

```sh
npm run studio:import-posts
```

## Projects

Copy `src/content/projects/_template.md`, rename it, set `draft: false`, and add project details.

## Secrets

Porkbun API keys and any Sanity read token are stored in `.env.local`. Do not commit that file.
