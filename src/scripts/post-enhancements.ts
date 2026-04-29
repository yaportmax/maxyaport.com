import EmblaCarousel from "embla-carousel";
import Autoplay from "embla-carousel-autoplay";
import gsap from "gsap";
import ScrollTrigger from "gsap/ScrollTrigger";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import PhotoSwipeLightbox from "photoswipe/lightbox";
import "photoswipe/style.css";
import {along, bbox, distance, length, lineString, point} from "@turf/turf";

type CarouselSettings = {
  loop?: boolean;
  autoplay?: boolean;
  autoplayDelay?: number;
  variableWidths?: boolean;
  dragFree?: boolean;
  parallax?: boolean;
  opacity?: boolean;
  columns?: number;
};

type RoutePayload = {
  title?: string;
  center?: {lat: number; lng: number};
  zoom?: number;
  markers?: Array<{label?: string; lat: number; lng: number}>;
  routeLabels?: Array<{label?: string; mile: number}>;
  gpxUrl?: string;
  mileStart?: number;
  mileEnd?: number;
  animation?: string;
  mood?: string;
  showElevation?: boolean;
};

type TrackPoint = {
  lng: number;
  lat: number;
  ele?: number;
};

type ProjectedPoint = {
  x: number;
  y: number;
};

gsap.registerPlugin(ScrollTrigger);

const mapboxToken = import.meta.env.PUBLIC_MAPBOX_TOKEN || "";
if (mapboxToken) {
  mapboxgl.accessToken = mapboxToken;
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);
const gpxCache = new Map<string, Promise<TrackPoint[]>>();
const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function readJsonAttribute<T>(element: Element, name: string, fallback: T): T {
  try {
    return JSON.parse(element.getAttribute(name) || "") as T;
  } catch {
    return fallback;
  }
}

function initEmblaCarousels() {
  document.querySelectorAll<HTMLElement>("[data-embla-carousel]").forEach((root) => {
    const viewport = root.querySelector<HTMLElement>(".embla__viewport");
    if (!viewport) return;

    const settings = readJsonAttribute<CarouselSettings>(root, "data-embla-carousel", {});
    const plugins = settings.autoplay
      ? [
          Autoplay({
            delay: settings.autoplayDelay || 4200,
            stopOnInteraction: true,
            stopOnMouseEnter: true,
          }),
        ]
      : [];

    const embla = EmblaCarousel(
      viewport,
      {
        loop: Boolean(settings.loop),
        dragFree: Boolean(settings.dragFree),
        align: "start",
        containScroll: settings.loop ? false : "trimSnaps",
      },
      plugins,
    );

    const slides = embla.slideNodes();
    const imageLayers = slides.map((slide) => slide.querySelector<HTMLElement>(".embla__slide__img"));
    const caption = root.querySelector<HTMLElement>("[data-carousel-caption]");

    const updateEffects = () => {
      const scrollProgress = embla.scrollProgress();
      const snaps = embla.scrollSnapList();
      const selectedSlide = slides[embla.selectedScrollSnap()];
      const selectedCaption =
        selectedSlide?.getAttribute("data-caption") ||
        caption?.getAttribute("data-default-caption") ||
        "";

      if (caption) {
        caption.textContent = selectedCaption;
        caption.hidden = !selectedCaption;
      }

      slides.forEach((slide, index) => {
        const snap = snaps[index] ?? 0;
        const diff = snap - scrollProgress;
        const distanceFromFocus = Math.abs(diff);

        if (settings.opacity) {
          slide.style.opacity = String(1 - Math.min(distanceFromFocus * 1.8, 0.52));
        }

        if (settings.parallax && imageLayers[index]) {
          imageLayers[index]!.style.transform = `translate3d(${diff * -64}px, 0, 0) scale(1.06)`;
        }
      });
    };

    updateEffects();
    embla.on("scroll", updateEffects);
    embla.on("select", updateEffects);
    embla.on("reInit", updateEffects);
  });
}

function initPhotoSwipe() {
  if (!document.querySelector(".pswp-gallery a")) return;

  const lightbox = new PhotoSwipeLightbox({
    gallery: ".pswp-gallery",
    children: "a",
    pswpModule: () => import("photoswipe"),
  });
  lightbox.init();
}

function parseGpx(gpxText: string): TrackPoint[] {
  const documentXml = new DOMParser().parseFromString(gpxText, "application/xml");
  const nodes = Array.from(documentXml.querySelectorAll("trkpt, rtept"));

  return nodes
    .map((node) => {
      const lat = Number(node.getAttribute("lat"));
      const lng = Number(node.getAttribute("lon"));
      const eleText = node.querySelector("ele")?.textContent;
      const ele = eleText ? Number(eleText) : undefined;
      return Number.isFinite(lat) && Number.isFinite(lng) ? {lat, lng, ele} : null;
    })
    .filter((value): value is TrackPoint => Boolean(value));
}

async function loadGpx(url: string) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not fetch GPX: ${url}`);
  return parseGpx(await response.text());
}

function loadCachedGpx(url: string) {
  if (!gpxCache.has(url)) {
    const request = loadGpx(url).catch((error) => {
      gpxCache.delete(url);
      throw error;
    });
    gpxCache.set(url, request);
  }
  return gpxCache.get(url)!;
}

function cumulativeMiles(points: TrackPoint[]) {
  const miles = [0];
  for (let index = 1; index < points.length; index += 1) {
    const previous = point([points[index - 1].lng, points[index - 1].lat]);
    const current = point([points[index].lng, points[index].lat]);
    miles.push(miles[index - 1] + distance(previous, current, {units: "miles"}));
  }
  return miles;
}

function segmentCoordinates(points: TrackPoint[], startMile = 0, endMile?: number) {
  const coords = points.map((trackPoint) => [trackPoint.lng, trackPoint.lat]);
  if (coords.length < 2) return coords;

  const route = lineString(coords);
  const totalMiles = length(route, {units: "miles"});
  const start = clamp(startMile, 0, totalMiles);
  const end = clamp(endMile ?? totalMiles, start, totalMiles);
  const miles = cumulativeMiles(points);
  const segment = [along(route, start, {units: "miles"}).geometry.coordinates];

  for (let index = 0; index < points.length; index += 1) {
    if (miles[index] > start && miles[index] < end) {
      segment.push(coords[index]);
    }
  }

  segment.push(along(route, end, {units: "miles"}).geometry.coordinates);
  return segment;
}

function partialCoordinates(coords: number[][], progress: number) {
  if (coords.length < 2 || progress >= 0.995) return coords;

  const route = lineString(coords);
  const totalMiles = length(route, {units: "miles"});
  const targetMiles = totalMiles * clamp(progress, 0, 1);
  const partial = [coords[0]];
  let traveled = 0;

  for (let index = 1; index < coords.length; index += 1) {
    const step = distance(point(coords[index - 1]), point(coords[index]), {units: "miles"});
    if (traveled + step >= targetMiles) break;
    traveled += step;
    partial.push(coords[index]);
  }

  partial.push(along(route, targetMiles, {units: "miles"}).geometry.coordinates);
  return partial;
}

function profileSvg(points: TrackPoint[], startMile = 0, endMile?: number) {
  const elevations = points.map((trackPoint) => trackPoint.ele).filter((value): value is number => Number.isFinite(value));
  if (elevations.length < 2) return "";

  const width = 720;
  const height = 128;
  const pad = 10;
  const miles = cumulativeMiles(points);
  const totalMiles = miles[miles.length - 1] || 1;
  const minElevation = Math.min(...elevations);
  const maxElevation = Math.max(...elevations);
  const range = Math.max(maxElevation - minElevation, 1);
  const pointsAttr = points
    .map((trackPoint, index) => {
      const x = pad + (miles[index] / totalMiles) * (width - pad * 2);
      const y = height - pad - (((trackPoint.ele || minElevation) - minElevation) / range) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const highlightStart = pad + (clamp(startMile, 0, totalMiles) / totalMiles) * (width - pad * 2);
  const highlightEnd =
    pad + (clamp(endMile ?? totalMiles, 0, totalMiles) / totalMiles) * (width - pad * 2);
  const highlightWidth = Math.max(highlightEnd - highlightStart, 4);

  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Elevation profile">
    <rect class="elevation-highlight" x="${highlightStart.toFixed(1)}" y="0" width="${highlightWidth.toFixed(1)}" height="${height}" />
    <polyline class="elevation-line" points="${pointsAttr}" />
  </svg>`;
}

function addMarker(map: mapboxgl.Map, lngLat: [number, number], className: string, label?: string) {
  const markerElement = document.createElement("div");
  markerElement.className = className;
  if (label) markerElement.textContent = label;
  return new mapboxgl.Marker({element: markerElement}).setLngLat(lngLat).addTo(map);
}

function routeShouldAnimate(payload: RoutePayload) {
  return payload.animation !== "static" && !prefersReducedMotion();
}

function projectionFor(bounds: number[], width = 1000, height = 520) {
  const padding = {top: 126, right: 70, bottom: 126, left: 70};
  const [minLng, minLat, maxLng, maxLat] = bounds;
  const latMid = ((minLat + maxLat) / 2) * (Math.PI / 180);
  const latScale = Math.max(Math.cos(latMid), 0.2);
  const minX = minLng * latScale;
  const maxX = maxLng * latScale;
  const minY = minLat;
  const maxY = maxLat;
  const rangeX = Math.max(maxX - minX, 0.00001);
  const rangeY = Math.max(maxY - minY, 0.00001);
  const scale = Math.min(
    (width - padding.left - padding.right) / rangeX,
    (height - padding.top - padding.bottom) / rangeY,
  );
  const usedWidth = rangeX * scale;
  const usedHeight = rangeY * scale;
  const offsetX = padding.left + (width - padding.left - padding.right - usedWidth) / 2;
  const offsetY = padding.top + (height - padding.top - padding.bottom - usedHeight) / 2;

  return ([lng, lat]: number[]): ProjectedPoint => ({
    x: offsetX + (lng * latScale - minX) * scale,
    y: height - (offsetY + (lat - minY) * scale),
  });
}

function pathData(points: ProjectedPoint[]) {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");
}

function svgElement<K extends keyof SVGElementTagNameMap>(name: K) {
  return document.createElementNS("http://www.w3.org/2000/svg", name);
}

function createRouteOverlay(
  card: HTMLElement,
  routeLine: GeoJSON.Feature<GeoJSON.LineString>,
  segmentLine: GeoJSON.Feature<GeoJSON.LineString>,
  payload: RoutePayload,
) {
  const width = 1000;
  const height = 520;
  const boundsSource = payload.mileStart !== undefined || payload.mileEnd !== undefined ? segmentLine : routeLine;
  const project = projectionFor(bbox(boundsSource), width, height);
  const fullPoints = routeLine.geometry.coordinates.map(project);
  const segmentPoints = segmentLine.geometry.coordinates.map(project);
  const overlay = document.createElement("div");
  overlay.className = "route-card__overlay";

  const svg = svgElement("svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("aria-hidden", "true");

  const fullPath = svgElement("path");
  fullPath.setAttribute("class", "route-overlay__line route-overlay__line--full");
  fullPath.setAttribute("d", pathData(fullPoints));
  svg.append(fullPath);

  const segmentPath = svgElement("path");
  segmentPath.setAttribute("class", "route-overlay__line route-overlay__line--segment");
  segmentPath.setAttribute("d", pathData(segmentPoints));
  svg.append(segmentPath);

  const progressPath = svgElement("path");
  progressPath.setAttribute("class", "route-overlay__line route-overlay__line--progress");
  progressPath.setAttribute("d", pathData(segmentPoints));
  svg.append(progressPath);

  const labelGroup = svgElement("g");
  labelGroup.setAttribute("class", "route-overlay__labels");
  const labelElements: SVGGElement[] = [];
  const routeMiles = length(routeLine, {units: "miles"});

  for (const routeLabel of payload.routeLabels || []) {
    if (!routeLabel?.label || typeof routeLabel.mile !== "number") continue;
    const start = payload.mileStart ?? 0;
    const end = payload.mileEnd ?? routeMiles;
    if (routeLabel.mile < start - 0.25 || routeLabel.mile > end + 0.25) continue;

    const labelCoordinate = along(routeLine, routeLabel.mile, {units: "miles"}).geometry.coordinates;
    const labelPoint = project(labelCoordinate);
    const label = svgElement("g");
    label.setAttribute("class", "route-overlay__label");
    label.setAttribute("transform", `translate(${labelPoint.x.toFixed(1)} ${labelPoint.y.toFixed(1)})`);
    const dot = svgElement("circle");
    dot.setAttribute("r", "5");
    const text = svgElement("text");
    text.setAttribute("x", "10");
    text.setAttribute("y", "-10");
    text.textContent = routeLabel.label;
    label.append(dot, text);
    labelGroup.append(label);
    labelElements.push(label);
  }

  svg.append(labelGroup);

  const marker = svgElement("circle");
  marker.setAttribute("class", "route-overlay__marker");
  marker.setAttribute("r", "8");
  svg.append(marker);
  overlay.append(svg);
  card.append(overlay);

  const pathLength = progressPath.getTotalLength();
  progressPath.style.strokeDasharray = String(pathLength);
  const progress = {value: routeShouldAnimate(payload) ? 0 : 1};

  const update = () => {
    const safeProgress = clamp(progress.value, 0, 1);
    progressPath.style.strokeDashoffset = String(pathLength * (1 - safeProgress));
    const markerPoint = progressPath.getPointAtLength(pathLength * safeProgress);
    marker.setAttribute("cx", String(markerPoint.x));
    marker.setAttribute("cy", String(markerPoint.y));
    card.style.setProperty("--route-progress", String(safeProgress));
  };

  update();

  if (routeShouldAnimate(payload)) {
    gsap.to(progress, {
      value: 1,
      ease: "none",
      scrollTrigger: {
        trigger: card,
        start: "top 78%",
        end: "bottom 32%",
        scrub: true,
      },
      onUpdate: update,
    });

    if (labelElements.length) {
      gsap.fromTo(
        labelElements,
        {autoAlpha: 0, y: 8},
        {
          autoAlpha: 1,
          y: 0,
          duration: 0.35,
          stagger: 0.08,
          ease: "power2.out",
          scrollTrigger: {
            trigger: card,
            start: "bottom 54%",
          },
        },
      );
    }
  } else if (labelElements.length) {
    gsap.set(labelElements, {autoAlpha: 1});
  }
}

function showRouteFallback(card: HTMLElement, message: string) {
  card.classList.add("route-card--error");
  const mapElement = card.querySelector<HTMLElement>(".route-card__map");
  if (!mapElement) return;
  mapElement.innerHTML = `<div class="route-card__fallback">${message}</div>`;
}

async function initRouteCard(card: HTMLElement) {
  const payload = readJsonAttribute<RoutePayload>(card, "data-route-card", {});
  const mapElement = card.querySelector<HTMLElement>(".route-card__map");
  const elevationElement = card.querySelector<HTMLElement>(".route-card__elevation");
  if (!mapElement) return;

  let points: TrackPoint[] = [];
  if (payload.gpxUrl) {
    try {
      points = await loadCachedGpx(payload.gpxUrl);
    } catch (error) {
      console.warn(error);
      showRouteFallback(card, "Route file could not be loaded.");
      return;
    }
  }

  const hasRoute = points.length > 1;
  if (payload.gpxUrl && !hasRoute) {
    showRouteFallback(card, "Route file did not include enough points.");
    return;
  }

  const fullCoords = hasRoute ? points.map((trackPoint) => [trackPoint.lng, trackPoint.lat]) : [];
  const routeLine = hasRoute ? lineString(fullCoords) : null;
  const segmentCoords = hasRoute
    ? segmentCoordinates(points, payload.mileStart || 0, payload.mileEnd)
    : [];
  const segmentLine = segmentCoords.length > 1 ? lineString(segmentCoords) : null;
  const routeBounds = routeLine ? bbox(routeLine) : null;
  const center = payload.center
    ? ([payload.center.lng, payload.center.lat] as [number, number])
    : hasRoute
      ? (segmentCoords[Math.floor(segmentCoords.length / 2)] as [number, number])
      : ([-120.9, 39] as [number, number]);

  if (elevationElement && payload.showElevation !== false && hasRoute) {
    elevationElement.innerHTML = profileSvg(points, payload.mileStart || 0, payload.mileEnd);
  }

  if (routeLine && segmentLine) {
    createRouteOverlay(card, routeLine, segmentLine, payload);
  }

  if (!mapboxToken) {
    mapElement.setAttribute("data-map-empty", "true");
    ScrollTrigger.refresh();
    return;
  }

  const map = new mapboxgl.Map({
    container: mapElement,
    style: "mapbox://styles/mapbox/outdoors-v12",
    center,
    zoom: payload.zoom || 9,
    attributionControl: false,
    interactive: false,
    antialias: true,
  });

  map.on("load", () => {
    map.resize();
    const labelElements: HTMLElement[] = [];

    if (routeLine && segmentLine) {
      map.addSource("route-full", {type: "geojson", data: routeLine});
      map.addSource("route-segment", {type: "geojson", data: segmentLine});
      map.addSource("route-progress", {
        type: "geojson",
        data: lineString(partialCoordinates(segmentCoords, payload.animation === "static" ? 1 : 0)),
      });
      map.addLayer({
        id: "route-full",
        type: "line",
        source: "route-full",
        paint: {
          "line-color": "#2c4231",
          "line-width": 2.4,
          "line-opacity": 0.58,
        },
      });
      map.addLayer({
        id: "route-segment",
        type: "line",
        source: "route-segment",
        paint: {
          "line-color": "#fff0c2",
          "line-width": 4.6,
          "line-opacity": 0.88,
        },
      });
      map.addLayer({
        id: "route-progress",
        type: "line",
        source: "route-progress",
        paint: {
          "line-color": payload.animation === "fast" ? "#f4d35e" : "#9fb77d",
          "line-width": payload.animation === "fast" ? 7 : 5,
          "line-opacity": 0.96,
        },
      });

      const boundsSource = payload.mileStart !== undefined || payload.mileEnd !== undefined ? segmentLine : routeLine;
      const [minLng, minLat, maxLng, maxLat] = bbox(boundsSource);
      map.fitBounds(
        [
          [minLng, minLat],
          [maxLng, maxLat],
        ],
        {padding: 42, duration: 0},
      );

      for (const routeLabel of payload.routeLabels || []) {
        if (!routeLabel?.label || typeof routeLabel.mile !== "number") continue;
        const start = payload.mileStart ?? 0;
        const end = payload.mileEnd ?? length(routeLine, {units: "miles"});
        if (routeLabel.mile < start - 0.25 || routeLabel.mile > end + 0.25) continue;

        const labelPoint = along(routeLine, routeLabel.mile, {units: "miles"}).geometry.coordinates as [
          number,
          number,
        ];
        const marker = addMarker(map, labelPoint, "route-label route-label--aid", routeLabel.label);
        labelElements.push(marker.getElement());
      }
    }

    for (const marker of payload.markers || []) {
      const renderedMarker = addMarker(map, [marker.lng, marker.lat], "route-label route-label--manual", marker.label);
      labelElements.push(renderedMarker.getElement());
    }

    const movingMarker = segmentCoords.length
      ? addMarker(map, segmentCoords[0] as [number, number], "route-marker")
      : null;
    const shouldAnimate = routeShouldAnimate(payload);
    const progress = {value: shouldAnimate ? 0 : 1};
    const source = map.getSource("route-progress") as mapboxgl.GeoJSONSource | undefined;

    const update = () => {
      if (!segmentLine || !source || !movingMarker) return;
      const safeProgress = clamp(progress.value, 0, 1);
      source.setData(lineString(partialCoordinates(segmentCoords, safeProgress)));
      const totalMiles = length(segmentLine, {units: "miles"});
      const markerPoint = along(segmentLine, totalMiles * safeProgress, {units: "miles"}).geometry
        .coordinates as [number, number];
      movingMarker.setLngLat(markerPoint);
      card.style.setProperty("--route-progress", String(safeProgress));
    };

    update();

    if (shouldAnimate) {
      gsap.to(progress, {
        value: 1,
        ease: "none",
        scrollTrigger: {
          trigger: card,
          start: "top 78%",
          end: "bottom 32%",
          scrub: true,
        },
        onUpdate: update,
      });

      if (labelElements.length) {
        gsap.fromTo(
          labelElements,
          {autoAlpha: 0, y: 8},
          {
            autoAlpha: 1,
            y: 0,
            duration: 0.35,
            stagger: 0.08,
            ease: "power2.out",
            scrollTrigger: {
              trigger: card,
              start: "bottom 54%",
            },
          },
        );
      }
    } else if (labelElements.length) {
      gsap.set(labelElements, {autoAlpha: 1});
    }

    ScrollTrigger.refresh();
  });

  map.on("error", (event) => {
    console.warn("Mapbox route card error", event.error);
  });
}

function initRouteCards() {
  const cards = Array.from(document.querySelectorAll<HTMLElement>("[data-route-card]"));
  const started = new WeakSet<HTMLElement>();
  const startCard = (card: HTMLElement) => {
    if (started.has(card)) return;
    started.add(card);
    void initRouteCard(card);
  };

  if (!("IntersectionObserver" in window)) {
    cards.forEach(startCard);
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const card = entry.target as HTMLElement;
        observer.unobserve(card);
        startCard(card);
      }
    },
    {rootMargin: "700px 0px"},
  );

  cards.forEach((card) => observer.observe(card));
}

function initScrollReveals() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const media = gsap.matchMedia();
  media.add("(min-width: 1px)", () => {
    gsap.utils.toArray<HTMLElement>(".race-stats, .race-chapter, .photo-carousel").forEach((element) => {
      gsap.fromTo(
        element,
        {autoAlpha: 0.72, filter: "blur(5px)"},
        {
          autoAlpha: 1,
          filter: "blur(0px)",
          duration: 0.55,
          ease: "power2.out",
          scrollTrigger: {
            trigger: element,
            start: "top 86%",
          },
        },
      );
    });
  });
}

initEmblaCarousels();
initPhotoSwipe();
initRouteCards();
initScrollReveals();
