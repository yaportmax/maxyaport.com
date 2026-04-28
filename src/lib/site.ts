import { getCollection } from "astro:content";

export const site = {
  name: "Max Yaport",
  description: "Running / travel / projects",
  url: "https://maxyaport.com"
};

export const navItems: { href: string; label: string }[] = [];

export async function getWriting() {
  return (await getCollection("writing", ({ data }) => !data.draft)).sort(
    (a, b) => b.data.date.valueOf() - a.data.date.valueOf()
  );
}

export async function getProjects() {
  return (await getCollection("projects", ({ data }) => !data.draft)).sort(
    (a, b) => b.data.date.valueOf() - a.data.date.valueOf()
  );
}

export async function getRecent() {
  const [writing, projects] = await Promise.all([getWriting(), getProjects()]);

  return [
    ...writing.map((entry) => ({
      id: `writing-${entry.id}`,
      kind: "writing",
      title: entry.data.title,
      description: entry.data.description,
      date: entry.data.date,
      href: `/writing/${entry.id}/`
    })),
    ...projects.map((entry) => ({
      id: `project-${entry.id}`,
      kind: "project",
      title: entry.data.title,
      description: entry.data.description,
      date: entry.data.date,
      href: entry.data.url
    }))
  ].sort((a, b) => b.date.valueOf() - a.date.valueOf());
}

export function formatDate(date: Date) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC"
  }).format(date);
}
