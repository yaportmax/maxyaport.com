---
title: "Building an Adventure Map"
description: "A first stab at turning years of trips, races, and Strava routes into a cinematic travel map."
date: 2026-04-30
draft: true
---

The point of this project is pretty simple: I want the website to make travel feel a little more alive.

Two things I really value are exploration and visual storytelling. I love travel, trips, races, long drives, weird detours, and the feeling of seeing a place unfold for the first time. I also really appreciate cinematography: the way a camera move, a map, a cut, or a small visual detail can change a memory from something factual into something felt.

One idea for this site is to combine those two things. I do not just want to tell someone where I went. I want to build digital experiences that give them a taste of the adventure itself: the distance, the movement, the terrain, the route, the timing, and the way one place connects to the next.

I do not really know what all of this will become yet. This is the first stab.

## How This Started

I was trying to figure out what trip I wanted to write about first. There are a lot of candidates: road trips, races, backpacking weekends, international travel, Tahoe drives, desert trips, coastal drives, and a growing pile of Strava routes.

Before writing about any single one, I started going back through all of them. That eventually turned into a different project: a database of every trip I could remember, with dates, places, routes, stops, flights, drives, races, and activities.

Once that data existed, a normal list felt too flat. A trip is not just a title and a date. It has shape. It has direction. It has a start, a path, and a return. Sometimes it is a flight across the ocean. Sometimes it is a slow road trip up the coast. Sometimes it is a race route inside a bigger trip. Sometimes it is a short run in the middle of a week that gives the whole place a different texture.

So the travel page became a map.

## What It Is

The current version is an interactive 3D globe of my travel history.

It includes flights, car routes, boat routes, races, Strava activities, and the stops inside each trip. The goal is not just to put dots on a map. The goal is to show the actual movement between places.

Flights arc across the globe. Drives trace roads where route data exists. Boat segments trace water routes. Races can show their GPX course. Strava activities are rendered as route lines instead of generic heatmap blobs, so overlapping runs and rides build into a more subtle activity layer.

The timeline at the bottom lets you move through the history chronologically. Selecting something focuses the globe on that route. Play mode moves through the timeline automatically, with a moving marker that follows routes over time. There is also an experimental cinematic camera mode that tries to follow the route with smoother pans and closer zooms, especially on shorter activities.

It is still rough in places, but the basic idea is there: a map that behaves more like a visual story than a directory.

## Features

The travel map currently supports:

- A fullscreen Mapbox globe with satellite imagery and 3D terrain.
- Flights, cars, and boat route layers with distinct visual styles.
- Multi-stop trips, including road trips with many configurable nodes.
- Return-to-start handling for round trips.
- Actual route geometry for drives where routes have been calculated.
- Great-circle arcs for long flights.
- GPX-backed race routes.
- Strava route rendering for runs, hikes, walks, rides, skis, swims, kayaking, surfing, and other activities with route data.
- A route-shaped Strava heatmap where red represents foot-based activities and blue represents bike or machine-assisted activities, with overlap blending between them.
- Timeline scrubbing across all trips, races, and Strava activities.
- Playback mode with adjustable speed.
- A moving route marker during playback.
- A cinematic follow-camera mode.
- Popups for trips, races, and Strava activities.
- Strava activity links from route names.
- Handling for overlapping routes, so nearby or stacked routes can be cycled through without needing a giant selector.
- Mobile-oriented layout constraints so the map, timeline, popups, and controls fit inside the viewport.

The thing I care most about is that the data stays route-shaped. I do not want white blobs, generic clusters, or a map that only says "I was here." I want the visible paths to preserve the feeling of moving through a place.

## The Data

The core data model started as a JSON file of trips and races. Each trip can have:

- A title and description.
- A date or date range.
- A primary travel mode.
- A list of route nodes.
- A list of route segments between those nodes.
- Per-node visibility settings.
- Optional generated coordinates for routed legs.

That lets a trip be more than one dot. A road trip can include every major stop. A flight-plus-drive trip can be represented as separate segments. A race trip can connect the travel route to the actual race course. A Strava activity can sit inside the trip timeline instead of being treated as unrelated data.

There are also generated GeoJSON files for trip routes, race routes, Strava routes, and Strava heatmap segments. Those files let the browser load map-ready data without recalculating everything on every page load.

## The Stack

The site is built with Astro. The writing side is backed by Sanity, while the travel map itself is mostly a custom Astro page with client-side JavaScript.

The map is Mapbox GL JS. It uses globe projection, satellite styling, terrain, custom route layers, route highlights, popups, and timeline-driven camera movement. Mapbox is also used for route calculation and geocoding in the route-editing workflow.

The travel data lives mostly in JSON and GeoJSON:

- `src/data/travel-map.json` stores the trip and race records.
- `public/data/trip-routes.geojson` stores generated trip routes.
- `public/data/race-routes.geojson` stores GPX-derived race routes.
- `public/data/strava-routes.geojson` stores public-safe Strava route lines.
- `public/data/strava-line-heatmap.geojson` stores route-shaped overlap segments for the Strava layer.

Python scripts handle a lot of the data generation:

- Building trip route GeoJSON.
- Building race route GeoJSON from GPX files.
- Creating the Strava route layer from activity data.
- Creating the Strava line heatmap from overlapping route segments.

The frontend then pulls those generated files into Mapbox sources and layers. The timeline, playback, popups, route selection, route highlighting, camera logic, and layer toggles are custom JavaScript.

## What I Like About It

I like that this started as a writing problem and turned into an interface problem.

I was trying to decide what story to tell, but the trips themselves needed structure first. Once the structure existed, the map became a way to see patterns that a list would hide: how often I return to the Sierra, how many routes thread through the Central Coast, how races fit into bigger trips, how years of small activities stack into a personal geography.

There is something satisfying about seeing a trip as motion. A flight is not the same as a drive. A drive with ten stops is not the same as one marker. A race route is not the same as the weekend around it. A run in a city is not just a dot in that city.

The map makes those differences visible.

## What Is Next

I am not sure yet.

Part of me wants this to become a better trip archive. Part of me wants it to become a tool for writing richer race and travel recaps. Part of me wants to push harder into the cinematic side: route playback, camera movement, terrain, photos, elevation, sound, and tighter story chapters.

The larger goal is to make the website feel less like a static portfolio and more like a collection of small interactive experiences. A trip post could start with a route. A race recap could move through aid stations. A travel page could let you scrub through years of movement and see the shape of a life outdoors.

This version is not the final form. It is just the first working version of the idea: take the places, routes, races, and activities that usually sit in separate apps and turn them into one visual story.
