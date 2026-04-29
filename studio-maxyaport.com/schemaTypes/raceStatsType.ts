import {defineArrayMember, defineField, defineType} from 'sanity'

export const raceStatsType = defineType({
  name: 'raceStats',
  title: 'Race stats',
  type: 'object',
  fields: [
    defineField({
      name: 'label',
      title: 'Label',
      type: 'string',
      initialValue: 'Race stats',
    }),
    defineField({
      name: 'stats',
      title: 'Stats',
      type: 'array',
      of: [
        defineArrayMember({
          type: 'object',
          fields: [
            defineField({
              name: 'value',
              title: 'Value',
              type: 'string',
              validation: (rule) => rule.required(),
            }),
            defineField({
              name: 'label',
              title: 'Label',
              type: 'string',
              validation: (rule) => rule.required(),
            }),
          ],
          preview: {
            select: {
              title: 'value',
              subtitle: 'label',
            },
          },
        }),
      ],
      validation: (rule) => rule.min(1),
    }),
  ],
  preview: {
    select: {
      title: 'label',
      stats: 'stats',
    },
    prepare({title, stats}) {
      const count = Array.isArray(stats) ? stats.length : 0
      return {
        title: title || 'Race stats',
        subtitle: `${count} stat${count === 1 ? '' : 's'}`,
      }
    },
  },
})
