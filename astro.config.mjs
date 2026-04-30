import { defineConfig } from "astro/config";
import { spawn } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const travelDataPath = path.join(root, "src/data/travel-map.json");

const readRequestBody = (request) =>
  new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    request.on("error", reject);
  });

const sendJson = (response, statusCode, payload) => {
  response.statusCode = statusCode;
  response.setHeader("content-type", "application/json");
  response.end(JSON.stringify(payload));
};

const isFiniteCoordinate = (node) => Number.isFinite(Number(node?.lat)) && Number.isFinite(Number(node?.lon));

const showNodeOnMap = (node, defaultValue = true) => {
  if (node?.showOnMap === false) return false;
  if (node?.showOnMap === true) return true;
  return defaultValue;
};

const sameRouteCoordinate = (first, second) =>
  isFiniteCoordinate(first) &&
  isFiniteCoordinate(second) &&
  Math.abs(Number(first.lat) - Number(second.lat)) < 0.00001 &&
  Math.abs(Number(first.lon) - Number(second.lon)) < 0.00001;

const returnNodeForStart = (start, existing = {}) => ({
  title: `Return to ${String(start.title || "start")}`,
  lat: Number(start.lat),
  lon: Number(start.lon),
  showOnMap: showNodeOnMap(existing, false),
});

const routeNodesReturningToStart = (nodes) => {
  if (nodes.length < 2) return nodes;
  const start = nodes[0];
  const finalNode = nodes[nodes.length - 1];
  if (sameRouteCoordinate(start, finalNode)) {
    return [...nodes.slice(0, -1), returnNodeForStart(start, finalNode)];
  }
  return [...nodes, returnNodeForStart(start)];
};

const normalizeRouteConfig = (data) => {
  if (!data || !Array.isArray(data.trips) || !Array.isArray(data.races)) {
    throw new Error("Expected travel data with trips and races arrays.");
  }

  const normalized = structuredClone(data);
  for (const trip of normalized.trips) {
    const nodes = Array.isArray(trip.routeNodes)
      ? trip.routeNodes.filter(isFiniteCoordinate).map((node, index) => {
          const routeNode = {
            title: String(node.title || `Stop ${index + 1}`),
            lat: Number(node.lat),
            lon: Number(node.lon),
          };
          if (node.showOnMap === false || node.showOnMap === true) routeNode.showOnMap = node.showOnMap;
          return routeNode;
        })
      : [];

    trip.travelMode = trip.travelMode === "flight" ? "flight" : "drive";
    if (nodes.length >= 2) trip.routeNodes = routeNodesReturningToStart(nodes);

    const existingSegments = Array.isArray(trip.routeSegments) ? trip.routeSegments : [];
    const legCount = Math.max(0, (trip.routeNodes || []).length - 1);
    trip.routeSegments = Array.from({ length: legCount }, (_, index) => {
      const existing = existingSegments[index] || {};
      return { mode: ["flight", "sail", "train"].includes(existing.mode) ? existing.mode : "drive" };
    });
  }
  return normalized;
};

const runRouteBuilder = () =>
  new Promise((resolve, reject) => {
    const child = spawn("python3", ["scripts/build-trip-routes.py"], {
      cwd: root,
      env: process.env,
    });
    let output = "";
    let errorOutput = "";

    child.stdout.on("data", (chunk) => {
      output += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      errorOutput += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve(output.trim());
      else reject(new Error(errorOutput.trim() || output.trim() || `Route builder exited with ${code}.`));
    });
  });

const travelConfigEditorPlugin = () => ({
  name: "travel-config-editor",
  configureServer(server) {
    server.middlewares.use(async (request, response, next) => {
      const url = new URL(request.url || "/", "http://localhost");
      if (!url.pathname.startsWith("/api/travel-config")) {
        next();
        return;
      }

      try {
        if (request.method === "GET" && url.pathname === "/api/travel-config") {
          sendJson(response, 200, JSON.parse(await readFile(travelDataPath, "utf8")));
          return;
        }

        if (request.method === "POST" && url.pathname === "/api/travel-config/save") {
          const body = await readRequestBody(request);
          const normalized = normalizeRouteConfig(JSON.parse(body));
          await writeFile(travelDataPath, `${JSON.stringify(normalized, null, 2)}\n`);
          const routeBuilderOutput = await runRouteBuilder();
          sendJson(response, 200, { ok: true, routeBuilderOutput });
          return;
        }

        sendJson(response, 404, { error: "Unknown travel config endpoint." });
      } catch (error) {
        sendJson(response, 500, { error: error instanceof Error ? error.message : String(error) });
      }
    });
  },
});

export default defineConfig({
  site: "https://maxyaport.com",
  output: "static",
  vite: {
    plugins: [travelConfigEditorPlugin()],
  },
});
