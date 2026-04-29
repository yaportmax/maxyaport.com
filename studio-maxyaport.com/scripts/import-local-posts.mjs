import {createHash} from 'node:crypto'
import {createReadStream, existsSync, readFileSync, writeFileSync} from 'node:fs'
import {mkdir} from 'node:fs/promises'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {getCliClient} from 'sanity/cli'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const studioRoot = path.resolve(__dirname, '..')
const siteRoot = path.resolve(studioRoot, '..')
const contentDir = path.join(siteRoot, 'archive/markdown-posts')
const imageRoot = path.join(siteRoot, 'public')
const cacheDir = path.join(siteRoot, '.sanity-migration')
const assetCachePath = path.join(cacheDir, 'asset-map.json')

const client = getCliClient({apiVersion: '2026-04-28'})

const files = [
  'canyons-100k-truckee-week.md',
  'canyons-plan.md',
  'terigo-app-store.md',
]

const assetCache = existsSync(assetCachePath)
  ? JSON.parse(readFileSync(assetCachePath, 'utf8'))
  : {}

function key(prefix = 'k') {
  return `${prefix}${Math.random().toString(36).slice(2, 11)}`
}

function parseFrontmatter(source) {
  const match = source.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/)
  if (!match) throw new Error('Missing frontmatter')

  const data = {}
  for (const line of match[1].split('\n')) {
    const field = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/)
    if (!field) continue

    let value = field[2].trim()
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1)
    }
    if (value === 'true') data[field[1]] = true
    else if (value === 'false') data[field[1]] = false
    else data[field[1]] = value
  }

  return {data, body: match[2].trim()}
}

function slugFromFilename(filename) {
  return filename.replace(/\.(md|mdx)$/i, '').replace(/\s+1$/, '')
}

function attrsFromTag(tag) {
  const attrs = {}
  for (const attrMatch of tag.matchAll(/([A-Za-z_:][-A-Za-z0-9_:.]*)=(["'])(.*?)\2/g)) {
    attrs[attrMatch[1]] = attrMatch[3]
  }
  return attrs
}

function splitBlocks(markdown) {
  const blocks = []
  let index = 0

  while (index < markdown.length) {
    if (markdown.slice(index).startsWith('<figure')) {
      const end = markdown.indexOf('</figure>', index)
      if (end === -1) break
      blocks.push(markdown.slice(index, end + '</figure>'.length).trim())
      index = end + '</figure>'.length
      while (markdown[index] === '\n') index += 1
      continue
    }

    const nextFigure = markdown.indexOf('<figure', index)
    const chunk = markdown.slice(index, nextFigure === -1 ? markdown.length : nextFigure)
    for (const part of chunk.split(/\n{2,}/)) {
      const trimmed = part.trim()
      if (trimmed) blocks.push(trimmed)
    }
    if (nextFigure === -1) break
    index = nextFigure
  }

  return blocks
}

function blockFromText(text, style = 'normal') {
  const markDefs = []
  const children = []
  const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g
  let lastIndex = 0
  let match

  while ((match = linkPattern.exec(text))) {
    if (match.index > lastIndex) {
      children.push({_type: 'span', _key: key('s'), text: text.slice(lastIndex, match.index), marks: []})
    }
    const markKey = key('m')
    markDefs.push({_type: 'link', _key: markKey, href: match[2]})
    children.push({_type: 'span', _key: key('s'), text: match[1], marks: [markKey]})
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    children.push({_type: 'span', _key: key('s'), text: text.slice(lastIndex), marks: []})
  }

  return {
    _type: 'block',
    _key: key('b'),
    style,
    markDefs,
    children: children.length ? children : [{_type: 'span', _key: key('s'), text, marks: []}],
  }
}

async function uploadImage(src) {
  if (!src.startsWith('/')) throw new Error(`Expected local public image path, got ${src}`)

  const filePath = path.join(imageRoot, src.replace(/^\//, ''))
  if (!existsSync(filePath)) throw new Error(`Image not found: ${filePath}`)

  const buffer = readFileSync(filePath)
  const hash = createHash('sha256').update(buffer).digest('hex')
  if (assetCache[hash]) {
    return assetCache[hash]
  }

  const asset = await client.assets.upload('image', createReadStream(filePath), {
    filename: path.basename(filePath),
  })
  assetCache[hash] = asset._id
  await mkdir(cacheDir, {recursive: true})
  writeFileSync(assetCachePath, JSON.stringify(assetCache, null, 2))
  return asset._id
}

async function blockFromFigure(html) {
  const imgTags = [...html.matchAll(/<img\b[^>]*>/g)].map((match) => match[0])
  const images = []
  for (const tag of imgTags) {
    const attrs = attrsFromTag(tag)
    const assetId = await uploadImage(attrs.src)
    images.push({
      _key: key('i'),
      _type: 'object',
      image: {_type: 'image', asset: {_type: 'reference', _ref: assetId}},
      alt: attrs.alt || '',
    })
  }

  const caption = html.match(/<figcaption>([\s\S]*?)<\/figcaption>/)?.[1]?.trim() || ''
  const isCarousel = html.includes('photo-grid') || images.length > 1

  if (isCarousel) {
    const columns = html.includes('photo-grid--3') ? 3 : 2
    return {
      _type: 'carousel',
      _key: key('c'),
      columns,
      caption,
      images,
    }
  }

  const first = images[0]
  if (!first) return null

  return {
    _type: 'imageBlock',
    _key: key('img'),
    image: first.image,
    alt: first.alt,
    caption,
    layout: html.includes('photo-wide') ? 'wide' : 'standard',
  }
}

async function bodyFromMarkdown(markdown) {
  const body = []
  for (const block of splitBlocks(markdown)) {
    if (block.startsWith('<figure')) {
      const figureBlock = await blockFromFigure(block)
      if (figureBlock) body.push(figureBlock)
      continue
    }
    if (block.startsWith('## ')) {
      body.push(blockFromText(block.replace(/^##\s+/, ''), 'h2'))
      continue
    }
    if (block.startsWith('### ')) {
      body.push(blockFromText(block.replace(/^###\s+/, ''), 'h3'))
      continue
    }
    body.push(blockFromText(block.replace(/\n/g, ' ')))
  }
  return body
}

for (const filename of files) {
  const source = readFileSync(path.join(contentDir, filename), 'utf8')
  const {data, body} = parseFrontmatter(source)
  const slug = slugFromFilename(filename)
  const document = {
    _id: `post.${slug}`,
    _type: 'post',
    title: data.title || slug,
    description: data.description || '',
    date: data.date,
    draft: Boolean(data.draft),
    slug: {_type: 'slug', current: slug},
    url: data.url || undefined,
    body: await bodyFromMarkdown(body),
  }

  await client.createOrReplace(document)
  console.log(`Imported ${slug}`)
}
