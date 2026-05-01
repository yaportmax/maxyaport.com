import EmblaCarousel from "embla-carousel";
import Autoplay from "embla-carousel-autoplay";
import gsap from "gsap";
import ScrollTrigger from "gsap/ScrollTrigger";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import PhotoSwipeLightbox from "photoswipe/lightbox";
import "photoswipe/style.css";
import {along, bbox, bearing as turfBearing, distance, length, lineString, point} from "@turf/turf";

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
  followCamera?: boolean;
  globe?: boolean;
  pitch?: number;
  bearing?: number;
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
const defaultRouteColor = "#b7d39a";
const fastRouteColor = "#f4d35e";
const finishRouteColor = "#f0b07a";
const moodLightPresets: Record<string, string> = {
  overview: "dusk",
  cold: "dawn",
  good: "day",
  hard: "dusk",
  "weird-good": "day",
  finish: "night",
};

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

function progressLineColor(payload: RoutePayload) {
  if (payload.mood === "finish") return finishRouteColor;
  return payload.animation === "fast" || payload.mood === "weird-good" ? fastRouteColor : defaultRouteColor;
}

function progressLineGradient(progress: number, payload: RoutePayload) {
  const color = progressLineColor(payload);
  const transparent = color === fastRouteColor ? "rgba(244, 211, 94, 0)" : "rgba(183, 211, 154, 0)";
  const stop = clamp(progress, 0.0001, 0.9999);

  return ["step", ["line-progress"], color, stop, transparent];
}

function routeBearing(coords: number[][]) {
  if (coords.length < 2) return -18;

  const start = coords[Math.max(0, Math.floor(coords.length * 0.16))] || coords[0];
  const end = coords[Math.min(coords.length - 1, Math.floor(coords.length * 0.84))] || coords[coords.length - 1];
  return turfBearing(point(start), point(end));
}

function cardPadding(card: HTMLElement, payload?: RoutePayload) {
  const narrow = card.clientWidth < 640;
  if (payload?.mood === "overview") {
    return narrow
      ? {top: 132, right: 38, bottom: 146, left: 38}
      : {top: 172, right: 84, bottom: 150, left: 84};
  }

  return narrow
    ? {top: 118, right: 28, bottom: 136, left: 28}
    : {top: 108, right: 74, bottom: 142, left: 74};
}

function fitRouteBounds(
  map: mapboxgl.Map,
  card: HTMLElement,
  source: GeoJSON.Feature<GeoJSON.LineString>,
  bearing: number,
  pitch: number,
  payload: RoutePayload,
) {
  const [minLng, minLat, maxLng, maxLat] = bbox(source);
  map.fitBounds(
    [
      [minLng, minLat],
      [maxLng, maxLat],
    ],
    {
      padding: cardPadding(card, payload),
      duration: 0,
      bearing,
      pitch,
    },
  );
}

function applyCinematicTerrain(map: mapboxgl.Map, payload: RoutePayload) {
  try {
    const lightPreset = moodLightPresets[payload.mood || ""] || "dusk";
    if (typeof (map as any).setConfigProperty === "function") {
      (map as any).setConfigProperty("basemap", "lightPreset", lightPreset);
    }

    if (!map.getSource("mapbox-dem")) {
      map.addSource("mapbox-dem", {
        type: "raster-dem",
        url: "mapbox://mapbox.mapbox-terrain-dem-v1",
        tileSize: 512,
        maxzoom: 14,
      });
    }

    const terrainExaggeration =
      payload.mood === "overview" ? 1.35 : payload.mood === "weird-good" ? 1.82 : 1.62;
    map.setTerrain({source: "mapbox-dem", exaggeration: terrainExaggeration});
    map.setFog({
      color: payload.mood === "cold" ? "rgb(13, 17, 18)" : "rgb(12, 14, 11)",
      "high-color": payload.mood === "finish" ? "rgb(92, 72, 54)" : "rgb(76, 91, 74)",
      "horizon-blend": payload.mood === "overview" ? 0.08 : 0.16,
      "space-color": "rgb(2, 4, 5)",
      "star-intensity": payload.mood === "finish" ? 0.16 : 0.06,
    });
  } catch (error) {
    console.warn("Could not enable Mapbox terrain", error);
  }
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
  const isLabel = className.includes("route-label");
  return new mapboxgl.Marker({
    element: markerElement,
    anchor: isLabel ? "top" : "center",
    offset: isLabel ? [0, 12] : [0, 0],
  })
    .setLngLat(lngLat)
    .addTo(map);
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
  const progressMile = card.querySelector<HTMLElement>("[data-route-mile]");
  const mileStart = payload.mileStart ?? 0;
  const mileEnd = payload.mileEnd ?? routeMiles;

  const update = () => {
    const safeProgress = clamp(progress.value, 0, 1);
    progressPath.style.strokeDashoffset = String(pathLength * (1 - safeProgress));
    const markerPoint = progressPath.getPointAtLength(pathLength * safeProgress);
    marker.setAttribute("cx", String(markerPoint.x));
    marker.setAttribute("cy", String(markerPoint.y));
    card.style.setProperty("--route-progress", String(safeProgress));
    if (progressMile) {
      progressMile.textContent = `Mile ${(mileStart + (mileEnd - mileStart) * safeProgress).toFixed(1)}`;
    }
  };

  update();

  if (routeShouldAnimate(payload)) {
    gsap.to(progress, {
      value: 1,
      ease: "none",
      scrollTrigger: routeScrollTrigger(card),
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
            start: "top 68%",
          },
        },
      );
    }
  } else if (labelElements.length) {
    gsap.set(labelElements, {autoAlpha: 1});
  }
}

function routeScrollTrigger(card: HTMLElement) {
  return {
    trigger: card,
    start: "top 82%",
    end: "bottom 24%",
    scrub: 0.34,
    invalidateOnRefresh: true,
  };
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
  const routeCardBearing =
    typeof payload.bearing === "number" ? payload.bearing : hasRoute ? routeBearing(segmentCoords) : -18;
  const routeCardPitch =
    typeof payload.pitch === "number"
      ? payload.pitch
      : payload.mood === "overview"
        ? 45
        : payload.animation === "fast"
          ? 66
          : 58;

  if (elevationElement && payload.showElevation !== false && hasRoute) {
    elevationElement.innerHTML = profileSvg(points, payload.mileStart || 0, payload.mileEnd);
  }

  if (!mapboxToken) {
    if (routeLine && segmentLine) {
      createRouteOverlay(card, routeLine, segmentLine, payload);
    }
    mapElement.setAttribute("data-map-empty", "true");
    ScrollTrigger.refresh();
    return;
  }

  const map = new mapboxgl.Map({
    container: mapElement,
    style: "mapbox://styles/mapbox/standard-satellite",
    config: {
      basemap: {
        lightPreset: "dusk",
        showPointOfInterestLabels: false,
        showTransitLabels: false,
        showRoadLabels: true,
      },
    },
    center,
    zoom: payload.zoom || 9,
    pitch: routeCardPitch,
    bearing: routeCardBearing,
    projection: payload.globe ? "globe" : "mercator",
    attributionControl: false,
    interactive: false,
    antialias: true,
  });

  map.on("style.load", () => {
    applyCinematicTerrain(map, payload);
  });

  map.on("load", () => {
    map.resize();
    applyCinematicTerrain(map, payload);
    card.classList.add("route-card--map-ready");
    const labelElements: HTMLElement[] = [];

    if (routeLine && segmentLine) {
      map.addSource("route-full", {type: "geojson", data: routeLine});
      map.addSource("route-segment", {type: "geojson", data: segmentLine});
      map.addSource("route-progress", {
        type: "geojson",
        lineMetrics: true,
        data: segmentLine,
      });
      map.addLayer({
        id: "route-full-casing",
        type: "line",
        source: "route-full",
        paint: {
          "line-color": "#07100c",
          "line-width": 5.8,
          "line-opacity": 0.46,
          "line-blur": 0.4,
          "line-emissive-strength": 0.65,
        },
      });
      map.addLayer({
        id: "route-full",
        type: "line",
        source: "route-full",
        paint: {
          "line-color": "#f4ead1",
          "line-width": 2.2,
          "line-opacity": 0.44,
          "line-emissive-strength": 0.72,
        },
      });
      map.addLayer({
        id: "route-segment-casing",
        type: "line",
        source: "route-segment",
        paint: {
          "line-color": "#070907",
          "line-width": 12,
          "line-opacity": 0.62,
          "line-blur": 1.6,
          "line-emissive-strength": 0.7,
        },
      });
      map.addLayer({
        id: "route-segment",
        type: "line",
        source: "route-segment",
        paint: {
          "line-color": "#f3e5ba",
          "line-width": 5.8,
          "line-opacity": 0.74,
          "line-emissive-strength": 0.9,
        },
      });
      map.addLayer({
        id: "route-progress-glow",
        type: "line",
        source: "route-progress",
        paint: {
          "line-gradient": progressLineGradient(payload.animation === "static" ? 1 : 0, payload),
          "line-width": payload.animation === "fast" ? 17 : 14,
          "line-opacity": 0.36,
          "line-blur": 2.8,
          "line-emissive-strength": 1,
        },
      });
      map.addLayer({
        id: "route-progress",
        type: "line",
        source: "route-progress",
        paint: {
          "line-gradient": progressLineGradient(payload.animation === "static" ? 1 : 0, payload),
          "line-width": payload.animation === "fast" ? 9.2 : 7.8,
          "line-opacity": 0.96,
          "line-blur": 0.15,
          "line-emissive-strength": 1,
        },
      });

      const boundsSource = payload.mileStart !== undefined || payload.mileEnd !== undefined ? segmentLine : routeLine;
      fitRouteBounds(map, card, boundsSource, routeCardBearing, routeCardPitch, payload);

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
    const progressMile = card.querySelector<HTMLElement>("[data-route-mile]");
    const segmentMiles = segmentLine ? length(segmentLine, {units: "miles"}) : 0;
    const absoluteStartMile = payload.mileStart ?? 0;
    const absoluteEndMile = payload.mileEnd ?? absoluteStartMile + segmentMiles;
    let cameraState:
      | {lng: number; lat: number; zoom: number; pitch: number; bearing: number}
      | null = null;

    const updateFollowCamera = (markerPoint: [number, number], safeProgress: number) => {
      if (!segmentLine || !payload.followCamera || safeProgress <= 0.02 || safeProgress >= 0.98) return;

      const lookAhead = clamp(safeProgress + (payload.animation === "fast" ? 0.075 : 0.045), 0, 1);
      const aheadPoint = along(segmentLine, segmentMiles * lookAhead, {units: "miles"}).geometry
        .coordinates as [number, number];
      const dynamicBearing = Number.isFinite(turfBearing(point(markerPoint), point(aheadPoint)))
        ? turfBearing(point(markerPoint), point(aheadPoint))
        : routeCardBearing;
      const targetZoom =
        payload.mood === "weird-good"
          ? 11.35
          : payload.animation === "fast"
            ? 10.9
            : card.clientWidth < 640
              ? 10.2
              : 10.7;
      const targetPitch = payload.mood === "weird-good" ? Math.max(routeCardPitch, 70) : routeCardPitch;
      const target = {
        lng: markerPoint[0],
        lat: markerPoint[1],
        zoom: Math.max(map.getZoom(), targetZoom),
        pitch: targetPitch,
        bearing: dynamicBearing,
      };

      if (!cameraState) {
        cameraState = target;
      } else {
        const blend = payload.mood === "weird-good" ? 0.32 : 0.22;
        cameraState = {
          lng: cameraState.lng + (target.lng - cameraState.lng) * blend,
          lat: cameraState.lat + (target.lat - cameraState.lat) * blend,
          zoom: cameraState.zoom + (target.zoom - cameraState.zoom) * blend,
          pitch: cameraState.pitch + (target.pitch - cameraState.pitch) * blend,
          bearing: cameraState.bearing + (target.bearing - cameraState.bearing) * blend,
        };
      }

      map.jumpTo({
        center: [cameraState.lng, cameraState.lat],
        zoom: cameraState.zoom,
        pitch: cameraState.pitch,
        bearing: cameraState.bearing,
      });
    };

    const update = () => {
      if (!segmentLine || !movingMarker) return;
      const safeProgress = clamp(progress.value, 0, 1);
      if (map.getLayer("route-progress")) {
        const gradient = progressLineGradient(safeProgress, payload);
        map.setPaintProperty("route-progress", "line-gradient", gradient);
        if (map.getLayer("route-progress-glow")) {
          map.setPaintProperty("route-progress-glow", "line-gradient", gradient);
        }
      }
      const totalMiles = length(segmentLine, {units: "miles"});
      const markerPoint = along(segmentLine, totalMiles * safeProgress, {units: "miles"}).geometry
        .coordinates as [number, number];
      movingMarker.setLngLat(markerPoint);
      card.style.setProperty("--route-progress", String(safeProgress));
      if (progressMile) {
        progressMile.textContent = `Mile ${(absoluteStartMile + (absoluteEndMile - absoluteStartMile) * safeProgress).toFixed(1)}`;
      }

      updateFollowCamera(markerPoint, safeProgress);
    };

    update();

    if (shouldAnimate) {
      gsap.to(progress, {
        value: 1,
        ease: "none",
        scrollTrigger: routeScrollTrigger(card),
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
              start: "top 68%",
            },
          },
        );
      }
    } else if (labelElements.length) {
      gsap.set(labelElements, {autoAlpha: 1});
    }

    ScrollTrigger.refresh();
    ScrollTrigger.update();
    update();
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

function initCanyonsSoundscape() {
  const button = document.querySelector<HTMLButtonElement>("[data-canyons-audio]");
  if (!button) return;

  let audioContext: AudioContext | null = null;
  let gain: GainNode | null = null;
  let filter: BiquadFilterNode | null = null;
  let oscillator: OscillatorNode | null = null;
  let enabled = false;

  const scrollRatio = () => {
    const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    return clamp(window.scrollY / maxScroll, 0, 1);
  };

  const ensureAudio = () => {
    if (audioContext) return audioContext;
    const AudioCtor = window.AudioContext || (window as any).webkitAudioContext;
    audioContext = new AudioCtor();
    gain = audioContext.createGain();
    gain.gain.value = 0.0001;
    filter = audioContext.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 420;

    const buffer = audioContext.createBuffer(1, audioContext.sampleRate * 2, audioContext.sampleRate);
    const data = buffer.getChannelData(0);
    let last = 0;
    for (let index = 0; index < data.length; index += 1) {
      last = (last + (Math.random() * 2 - 1) * 0.035) * 0.985;
      data[index] = last;
    }

    const noise = audioContext.createBufferSource();
    noise.buffer = buffer;
    noise.loop = true;
    oscillator = audioContext.createOscillator();
    oscillator.type = "sine";
    oscillator.frequency.value = 72;
    const oscillatorGain = audioContext.createGain();
    oscillatorGain.gain.value = 0.012;

    noise.connect(filter);
    filter.connect(gain);
    oscillator.connect(oscillatorGain);
    oscillatorGain.connect(gain);
    gain.connect(audioContext.destination);
    noise.start();
    oscillator.start();
    return audioContext;
  };

  const updateAudio = () => {
    if (!audioContext || !gain || !filter || !oscillator || !enabled) return;
    const progress = scrollRatio();
    const intensity = 0.5 + Math.sin(progress * Math.PI) * 0.5;
    gain.gain.setTargetAtTime(0.028 + intensity * 0.025, audioContext.currentTime, 0.24);
    filter.frequency.setTargetAtTime(340 + progress * 620, audioContext.currentTime, 0.3);
    oscillator.frequency.setTargetAtTime(58 + progress * 34, audioContext.currentTime, 0.3);
  };

  button.addEventListener("click", async () => {
    const context = ensureAudio();
    enabled = !enabled;
    button.setAttribute("aria-pressed", String(enabled));
    document.body.classList.toggle("canyons-audio-active", enabled);
    if (enabled) {
      await context.resume();
      updateAudio();
    } else {
      gain?.gain.setTargetAtTime(0.0001, context.currentTime, 0.18);
      await context.suspend();
    }
  });

  window.addEventListener("scroll", updateAudio, {passive: true});
}

initEmblaCarousels();
initPhotoSwipe();
initRouteCards();
initScrollReveals();
initCanyonsSoundscape();
