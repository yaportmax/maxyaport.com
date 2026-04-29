# maxyaport.com Codex Project Reference

Use this folder as the stable reference material for a Codex Project focused on `maxyaport.com`.

The actual website repo root is:

```txt
/Users/myaport/Documents/maxyaport-codex-project
```

The live site is:

```txt
https://maxyaport.com
```

## Current Direction

- Use Sanity Studio for writing and long-form editing.
- Keep Sanity as the source of truth for posts.
- Keep archived Markdown posts only as backup/reference material.
- Use Sanity image and carousel blocks for post media.
- Do not rely on chat history for site structure. Use this folder and the repo files.

## Main Commands

Run these from the website repo root:

```sh
npm install
npm run dev
npm run build
```

Sanity Studio:

```sh
npm run studio
```

Open `http://localhost:3333`.

## Important Files

```txt
archive/markdown-posts/canyons-100k-truckee-week.md
archive/markdown-posts/canyons-plan.md
archive/markdown-posts/terigo-app-store.md
studio-maxyaport.com/schemaTypes/
src/components/HomeContent.astro
src/components/WritingList.astro
src/components/RecentList.astro
src/pages/writing/[slug].astro
src/pages/travel.astro
src/styles/global.css
src/data/travel-map.json
public/images/
```

## Git And Deploy Rules

- Use `yaportmax@gmail.com` for commits.
- Do not commit with `myaport@magnite.com`.
- Do not commit `.env.local`, `.sanity-migration/`, `.strava-work/`, `.photo-work/`, `photo-review/`, `dist/`, or `node_modules/`.
- Do not expose pasted Strava, Mapbox secret, Porkbun, or Vercel credentials.
- Build before deploy.
- Verify the live site after deploy.

## Current Content Style

- First person, direct, not polished into marketing copy.
- No em dashes.
- Avoid AI-sounding summary language.
- Keep race/travel writing specific and concrete.
- Preserve user-provided names, captions, and ordering unless asked to revise.

## Sanity Writing Workflow

Run:

```sh
npm run studio
```

Open:

```txt
http://localhost:3333
```

After editing in Sanity:

```sh
npm run build
```

For local preview:

```sh
npm run dev
```
