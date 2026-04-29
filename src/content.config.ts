import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";

const projects = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/projects" }),
  schema: z.object({
    title: z.string(),
    description: z.string().default(""),
    date: z.date(),
    url: z.string().url().optional(),
    draft: z.boolean().default(false)
  })
});

export const collections = { projects };
