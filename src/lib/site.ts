import { getCollection } from "astro:content";
import { getSanityPosts } from "./sanity";

export const site = {
  name: "Max Yaport",
  description: "Running / travel / projects",
  url: "https://maxyaport.com"
};

export const navItems: { href: string; label: string }[] = [
  { href: "/travel/", label: "travel" }
];

export async function getWriting() {
  return (await getSanityPosts()).sort((a, b) => b.date.valueOf() - a.date.valueOf());
}

export async function getProjects() {
  return (await getCollection("projects", ({ data }) => !data.draft)).sort(
    (a, b) => b.data.date.valueOf() - a.data.date.valueOf()
  );
}

export async function getRecent() {
  const [writing, projects] = await Promise.all([
    getWriting(),
    getProjects()
  ]);

  const items = [
    ...writing.map((entry) => ({
      id: `sanity-writing-${entry.slug}`,
      kind: "writing",
      title: entry.title,
      description: entry.description,
      date: entry.date,
      href: entry.url ?? `/writing/${entry.slug}/`
    })),
    ...projects.map((entry) => ({
      id: `project-${entry.id}`,
      kind: "project",
      title: entry.data.title,
      description: entry.data.description,
      date: entry.data.date,
      href: entry.data.url
    }))
  ];

  return items.sort((a, b) => b.date.valueOf() - a.date.valueOf());
}

export function formatDate(date: Date) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC"
  }).format(date);
}
