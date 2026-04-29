import {createClient} from "@sanity/client";
import {createImageUrlBuilder} from "@sanity/image-url";
import {escapeHTML, toHTML, uriLooksSafe} from "@portabletext/to-html";

const projectId = import.meta.env.PUBLIC_SANITY_PROJECT_ID || "7hp5vphl";
const dataset = import.meta.env.PUBLIC_SANITY_DATASET || "production";
const apiVersion = "2026-04-28";

export interface SanityPost {
  source: "sanity";
  id: string;
  title: string;
  description: string;
  date: Date;
  slug: string;
  url?: string;
  html: string;
}

interface SanityRawPost {
  _id: string;
  title?: string;
  description?: string;
  date?: string;
  slug?: string;
  url?: string;
  body?: any[];
}

const client = createClient({
  projectId,
  dataset,
  apiVersion,
  useCdn: false,
  token: import.meta.env.SANITY_READ_TOKEN,
});

const imageBuilder = createImageUrlBuilder(client);

const imageProjection = `{
  ...,
  asset->{
    _id,
    url,
    metadata {
      dimensions
    }
  }
}`;

const postsQuery = `*[_type == "post" && !(_id in path("drafts.**"))] | order(date desc) {
  _id,
  title,
  description,
  date,
  "slug": slug.current,
  url,
  body[] {
    ...,
    image ${imageProjection},
    gpxFile {
      asset->{
        url,
        originalFilename
      }
    },
    images[] {
      ...,
      image ${imageProjection}
    },
    photos[] {
      ...,
      image ${imageProjection}
    },
    body[] {
      ...,
      markDefs[] {
        ...
      },
      children[] {
        ...
      }
    }
  }
}`;

const canyonsGpxUrl = "/routes/canyons-2026.gpx";

const canyonsChapters: Record<string, any> = {
  "Race Start to Deadwood 1": {
    mileStart: 0,
    mileEnd: 10.1,
    mood: "cold",
    animation: "draw",
    callout: "Cold start, burned porta-potties, and the first real climbs.",
    routeLabels: [
      {label: "China Wall", mile: 0},
      {label: "Deadwood 1", mile: 10.1},
    ],
  },
  "Deadwood 1, Devil's Thumb, Swinging Bridge, and Back": {
    mileStart: 10.1,
    mileEnd: 24,
    mood: "good",
    animation: "marker",
    callout: "Out-and-back chaos, bib-name heckling, and still having fun.",
    routeLabels: [
      {label: "Deadwood 1", mile: 10.1},
      {label: "Devil's Thumb", mile: 12},
      {label: "Swinging Bridge", mile: 13.5},
      {label: "Devil's Thumb", mile: 15.1},
      {label: "Deadwood 2", mile: 18.3},
      {label: "Michigan Bluff", mile: 24},
    ],
  },
  "Michigan Bluff to Foresthill": {
    mileStart: 24,
    mileEnd: 30,
    mood: "hard",
    animation: "draw",
    callout: "The first real tactical decision of the day.",
    routeLabels: [
      {label: "Michigan Bluff", mile: 24},
      {label: "Foresthill", mile: 30},
    ],
  },
  "Foresthill to Cal 2": {
    mileStart: 30,
    mileEnd: 38.2,
    mood: "hard",
    animation: "marker",
    callout: "Hot, exposed, and starting to hurt.",
    routeLabels: [
      {label: "Foresthill", mile: 30},
      {label: "Cal 2", mile: 38.2},
    ],
  },
  "Cal 2 to Drivers Flat": {
    mileStart: 38.2,
    mileEnd: 47.5,
    mood: "hard",
    animation: "draw",
    callout: "Spacey, hyper-focused, and trying to keep moving.",
    routeLabels: [
      {label: "Cal 2", mile: 38.2},
      {label: "Drivers Flat", mile: 47.5},
    ],
  },
  "The Weird Good Part": {
    mileStart: 47.5,
    mileEnd: 55.5,
    mood: "weird-good",
    animation: "fast",
    callout: "103 people passed in 8 miles.",
    routeLabels: [
      {label: "Drivers Flat", mile: 47.5},
      {label: "Mammoth Bar", mile: 55.5},
    ],
  },
  "Mammoth Bar": {
    mileStart: 55.5,
    mileEnd: 59.1,
    mood: "hard",
    animation: "draw",
    callout: "The lowest part before the final push.",
    routeLabels: [
      {label: "Mammoth Bar", mile: 55.5},
      {label: "Confluence", mile: 59.1},
    ],
  },
  Finish: {
    mileStart: 59.1,
    mileEnd: 63.1,
    mood: "finish",
    animation: "finish",
    callout: "15:46, almost two hours ahead of the 17:30 plan.",
    routeLabels: [
      {label: "Confluence", mile: 59.1},
      {label: "Finish", mile: 63.1},
    ],
  },
};

function parseDate(value?: string) {
  if (!value) return new Date(0);
  return new Date(value.includes("T") ? value : `${value}T00:00:00.000Z`);
}

function attr(value: unknown) {
  return escapeHTML(String(value ?? ""));
}

function imageUrl(source: unknown, width: number) {
  if (!source) return "";
  return imageBuilder.image(source).width(width).auto("format").fit("max").url();
}

function imageDimensions(image: any) {
  return image?.asset?.metadata?.dimensions || {};
}

function gpxUrl(value: any) {
  return value?.gpxFile?.asset?.url || value?.gpxUrl || "";
}

function firstGpxUrl(body: any[] = []) {
  for (const block of body) {
    const direct = gpxUrl(block);
    if (direct) return direct;
  }
  return "";
}

function jsonAttr(value: unknown) {
  return attr(JSON.stringify(value));
}

function formatMile(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function renderImageBlock(value: any) {
  const src = imageUrl(value?.image, value?.layout === "wide" ? 1600 : 1200);
  const largeSrc = imageUrl(value?.image, 2200);
  if (!src) return "";

  const dimensions = imageDimensions(value?.image);
  const width = Number(dimensions.width) || 1600;
  const height = Number(dimensions.height) || 1100;
  const figureClass = value?.layout === "wide" ? ' class="photo-wide pswp-gallery"' : ' class="pswp-gallery"';
  const alt = attr(value?.alt || value?.caption || "Post image");
  const caption = value?.caption ? `<figcaption>${attr(value.caption)}</figcaption>` : "";

  return `<figure${figureClass}><a href="${attr(largeSrc || src)}" data-pswp-width="${width}" data-pswp-height="${height}"><img src="${attr(src)}" alt="${alt}" loading="lazy" /></a>${caption}</figure>`;
}

function carouselSettings(value: any) {
  return {
    loop: Boolean(value?.loop),
    autoplay: Boolean(value?.autoplay),
    autoplayDelay: Number(value?.autoplayDelay) || 4200,
    variableWidths: Boolean(value?.variableWidths),
    dragFree: Boolean(value?.dragFree),
    parallax: Boolean(value?.parallax),
    opacity: Boolean(value?.opacity),
    columns: value?.columns === 3 ? 3 : 2,
  };
}

function renderCarousel(value: any) {
  const images = Array.isArray(value?.images) ? value.images : [];
  const settings = carouselSettings(value);
  const firstSlideCaption = images.find((item: any) => item?.caption)?.caption || "";
  const fallbackCaption = value?.caption || firstSlideCaption;
  const slides = images
    .map((item: any, index: number) => {
      const src = imageUrl(item?.image, 1200);
      const largeSrc = imageUrl(item?.image, 2200);
      if (!src) return "";

      const dimensions = imageDimensions(item?.image);
      const width = Number(dimensions.width) || 1600;
      const height = Number(dimensions.height) || 1100;
      const alt = attr(item?.alt || item?.caption || value?.caption || "Post image");
      const widthClass = settings.variableWidths && index % 3 === 1 ? " embla__slide--wide" : "";
      const slideCaption = attr(item?.caption || value?.caption || "");

      return `<div class="embla__slide${widthClass}" data-caption="${slideCaption}"><a href="${attr(largeSrc || src)}" data-pswp-width="${width}" data-pswp-height="${height}"><img class="embla__slide__img" src="${attr(src)}" alt="${alt}" loading="lazy" /></a></div>`;
    })
    .filter(Boolean)
    .join("");

  if (!slides) return "";

  const caption = fallbackCaption
    ? `<figcaption data-carousel-caption data-default-caption="${attr(value?.caption || "")}">${attr(fallbackCaption)}</figcaption>`
    : "";
  return `<figure class="photo-carousel photo-carousel--${settings.columns} pswp-gallery" data-embla-carousel="${jsonAttr(settings)}"><div class="embla__viewport"><div class="embla__container">${slides}</div></div>${caption}</figure>`;
}

function routePayload(value: any, overrides: Record<string, unknown> = {}) {
  const center = value?.center;
  const markers = Array.isArray(value?.markers)
    ? value.markers
        .filter((marker: any) => typeof marker?.lat === "number" && typeof marker?.lng === "number")
        .map((marker: any) => ({
          label: marker.label || "",
          lat: marker.lat,
          lng: marker.lng,
        }))
    : [];

  return {
    title: value?.title || "",
    caption: value?.caption || "",
    center:
      typeof center?.lat === "number" && typeof center?.lng === "number"
        ? {lat: center.lat, lng: center.lng}
        : undefined,
    zoom: typeof value?.zoom === "number" ? value.zoom : 9,
    markers,
    routeLabels: Array.isArray(value?.routeLabels) ? value.routeLabels : [],
    gpxUrl: gpxUrl(value),
    mileStart: typeof value?.mileStart === "number" ? value.mileStart : undefined,
    mileEnd: typeof value?.mileEnd === "number" ? value.mileEnd : undefined,
    showElevation: value?.showElevation !== false,
    animation: value?.animation || value?.mapAnimation || "draw",
    globe: value?.globe === true,
    followCamera: value?.followCamera === true,
    pitch: typeof value?.pitch === "number" ? value.pitch : undefined,
    bearing: typeof value?.bearing === "number" ? value.bearing : undefined,
    mood: value?.mood || "neutral",
    height: value?.height || "standard",
    ...overrides,
  };
}

function renderRouteCard(payload: any, caption = "") {
  const title = payload.title ? `<h3>${attr(payload.title)}</h3>` : "";
  const mileRange =
    typeof payload.mileStart === "number" && typeof payload.mileEnd === "number"
      ? `<span>Miles ${formatMile(payload.mileStart)}-${formatMile(payload.mileEnd)}</span>`
      : "";
  const callout = payload.callout ? `<p>${attr(payload.callout)}</p>` : "";
  const figcaption = caption ? `<figcaption>${attr(caption)}</figcaption>` : "";

  return `<figure class="route-card route-card--${attr(payload.mood || "neutral")} route-card--${attr(payload.height || "standard")}" data-route-card="${jsonAttr(payload)}"><div class="route-card__map"></div><div class="route-card__scrim"></div><div class="route-card__meta">${title}${mileRange}${callout}</div><div class="route-card__elevation" aria-hidden="true"></div>${figcaption}</figure>`;
}

function renderMapBlock(value: any) {
  const payload = routePayload(value);
  if (!payload.gpxUrl && !payload.center) return "";
  return renderRouteCard(payload, value?.caption || "");
}

function renderRaceStats(value: any) {
  const stats = Array.isArray(value?.stats) ? value.stats : [];
  if (!stats.length) return "";

  const items = stats
    .map((stat: any) => `<div><strong>${attr(stat.value)}</strong><span>${attr(stat.label)}</span></div>`)
    .join("");
  const label = value?.label ? `<p>${attr(value.label)}</p>` : "";
  return `<section class="race-stats">${label}<div>${items}</div></section>`;
}

function renderRaceChapter(value: any) {
  const title = value?.title || "Race chapter";
  const body = Array.isArray(value?.body) ? renderPortableText(value.body) : "";
  const callout = value?.callout ? `<aside class="chapter-callout">${attr(value.callout)}</aside>` : "";
  const route = renderRouteCard(
    routePayload(value, {
      title,
      callout: value?.callout || "",
      showElevation: true,
    }),
  );
  const photos = Array.isArray(value?.photos) && value.photos.length
    ? renderCarousel({
        images: value.photos,
        caption: value?.photoCaption || "",
        columns: value?.carouselColumns || 2,
        loop: value?.carouselLoop,
        autoplay: value?.carouselAutoplay,
        autoplayDelay: value?.carouselAutoplayDelay,
        dragFree: value?.carouselDragFree,
        variableWidths: value?.carouselVariableWidths ?? true,
        parallax: value?.carouselParallax ?? true,
        opacity: value?.carouselOpacity ?? true,
      })
    : "";

  return `<section class="race-chapter race-chapter--${attr(value?.mood || "neutral")}"><h2>${attr(title)}</h2><div class="race-chapter__text">${body}</div>${route}${photos}${callout}</section>`;
}

const portableComponents = {
  types: {
    imageBlock: ({value}: any) => renderImageBlock(value),
    carousel: ({value}: any) => renderCarousel(value),
    mapBlock: ({value}: any) => renderMapBlock(value),
    raceStats: ({value}: any) => renderRaceStats(value),
    raceChapter: ({value}: any) => renderRaceChapter(value),
  },
  marks: {
    link: ({children, value}: any) => {
      const href = value?.href || "";
      if (!uriLooksSafe(href)) return children;

      const rel = href.startsWith("/") ? "" : ' rel="noreferrer noopener"';
      const target = href.startsWith("/") ? "" : ' target="_blank"';
      return `<a href="${attr(href)}"${rel}${target}>${children}</a>`;
    },
  },
};

function renderPortableText(body: any[] = []) {
  return toHTML(body, {
    components: portableComponents,
  });
}

function textFromBlock(block: any) {
  if (block?._type !== "block") return "";
  return (block.children || []).map((child: any) => child.text || "").join("");
}

function isMediaBlock(block: any) {
  return block?._type === "imageBlock" || block?._type === "carousel";
}

function isCanyonsAutoGeneratedBlock(block: any) {
  return block?._type === "mapBlock" || block?._type === "raceStats" || block?._type === "raceChapter";
}

function renderCanyonsAutoChapter(title: string, blocks: any[], routeUrl: string) {
  const config = canyonsChapters[title];
  if (!config) {
    if (title === "Canyons 100k 10-15") {
      return "";
    }

    const contentBlocks = blocks.filter((block) => !isCanyonsAutoGeneratedBlock(block));
    return `<h2>${attr(title)}</h2>${renderPortableText(contentBlocks)}`;
  }

  const contentBlocks = blocks.filter((block) => !isCanyonsAutoGeneratedBlock(block));
  const textBlocks = contentBlocks.filter((block) => !isMediaBlock(block));
  const mediaBlocks = contentBlocks.filter(isMediaBlock);
  const route = renderRouteCard({
    title,
    gpxUrl: routeUrl,
    mileStart: config.mileStart,
    mileEnd: config.mileEnd,
    mood: config.mood,
    animation: config.animation,
    callout: config.callout,
    routeLabels: config.routeLabels || [],
    showElevation: true,
    height: title === "The Weird Good Part" ? "tall" : "standard",
  });
  const callout = config.callout ? `<aside class="chapter-callout">${attr(config.callout)}</aside>` : "";

  return `<section class="race-chapter race-chapter--${attr(config.mood)}"><h2>${attr(title)}</h2><div class="race-chapter__text">${renderPortableText(textBlocks)}</div>${route}${renderPortableText(mediaBlocks)}${callout}</section>`;
}

function renderCanyonsArticle(body: any[] = []) {
  const output: string[] = [];
  let index = 0;
  const routeUrl = canyonsGpxUrl;

  output.push(`<section class="canyons-hero-map">${renderRouteCard({
    title: "Canyons 100K",
    gpxUrl: routeUrl,
    mileStart: 0,
    mileEnd: 63.1,
    mood: "overview",
    animation: "draw",
    callout: "Auburn, Truckee, and 63.1 miles through the canyons.",
    routeLabels: [
      {label: "China Wall", mile: 0},
      {label: "Foresthill", mile: 30},
      {label: "Finish", mile: 63.1},
    ],
    showElevation: true,
    height: "tall",
  })}</section>`);
  output.push(renderRaceStats({
    label: "Race stats",
    stats: [
      {value: "15:46", label: "Finish time"},
      {value: "63.1 mi", label: "Course"},
    ],
  }));

  while (index < body.length) {
    const block = body[index];
    if (block?._type === "block" && block.style === "h2") {
      const title = textFromBlock(block);
      const sectionBlocks = [];
      index += 1;
      while (index < body.length) {
        const nextBlock = body[index];
        if (nextBlock?._type === "block" && nextBlock.style === "h2") break;
        sectionBlocks.push(nextBlock);
        index += 1;
      }
      output.push(renderCanyonsAutoChapter(title, sectionBlocks, routeUrl));
      continue;
    }

    if (isCanyonsAutoGeneratedBlock(block)) {
      index += 1;
      continue;
    }

    output.push(renderPortableText([block]));
    index += 1;
  }

  return output.join("");
}

function renderPostBody(post: SanityRawPost) {
  if (
    post._id === "post.canyons-100k-truckee-week" ||
    post.slug === "canyons-100k-truckee-week" ||
    post.slug === "canyons-100k-2026"
  ) {
    return renderCanyonsArticle(post.body || []);
  }
  return renderPortableText(post.body || []);
}

export async function getSanityPosts(): Promise<SanityPost[]> {
  try {
    const posts = await client.fetch<SanityRawPost[]>(postsQuery);
    return posts
      .filter((post) => post.title && post.slug && post.date)
      .map((post) => ({
        source: "sanity" as const,
        id: post._id,
        title: post.title || "",
        description: post.description || "",
        date: parseDate(post.date),
        slug: post.slug || "",
        url: post.url,
        html: renderPostBody(post),
      }));
  } catch (error) {
    console.warn("Could not load Sanity posts.", error);
    return [];
  }
}
