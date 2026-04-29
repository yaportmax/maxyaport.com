import {defineArrayMember, defineField, defineType} from 'sanity'

export const carouselType = defineType({
  name: 'carousel',
  title: 'Image carousel',
  type: 'object',
  fields: [
    defineField({
      name: 'images',
      title: 'Images',
      type: 'array',
      of: [
        defineArrayMember({
          type: 'object',
          fields: [
            defineField({
              name: 'image',
              title: 'Image',
              type: 'image',
              options: {hotspot: true},
              validation: (rule) => rule.required(),
            }),
            defineField({
              name: 'alt',
              title: 'Alt text',
              type: 'string',
            }),
            defineField({
              name: 'caption',
              title: 'Per-image note',
              type: 'string',
            }),
          ],
          preview: {
            select: {
              title: 'caption',
              media: 'image',
            },
            prepare({title, media}) {
              return {
                title: title || 'Carousel image',
                media,
              }
            },
          },
        }),
      ],
      validation: (rule) => rule.min(1),
    }),
    defineField({
      name: 'caption',
      title: 'Carousel caption',
      type: 'string',
    }),
    defineField({
      name: 'loop',
      title: 'Loop',
      description: 'Let the carousel wrap around from the last image to the first.',
      type: 'boolean',
      initialValue: false,
    }),
    defineField({
      name: 'autoplay',
      title: 'Autoplay',
      type: 'boolean',
      initialValue: false,
    }),
    defineField({
      name: 'autoplayDelay',
      title: 'Autoplay delay',
      description: 'Milliseconds between slides when autoplay is enabled.',
      type: 'number',
      initialValue: 4200,
      hidden: ({parent}) => !parent?.autoplay,
      validation: (rule) => rule.min(1200).max(15000),
    }),
    defineField({
      name: 'variableWidths',
      title: 'Variable widths',
      description: 'Use mixed slide widths for a more editorial rail.',
      type: 'boolean',
      initialValue: false,
    }),
    defineField({
      name: 'dragFree',
      title: 'Drag free',
      description: 'Allows a looser swipe instead of snapping hard to each slide.',
      type: 'boolean',
      initialValue: false,
    }),
    defineField({
      name: 'parallax',
      title: 'Parallax',
      description: 'Adds subtle image movement while swiping.',
      type: 'boolean',
      initialValue: false,
    }),
    defineField({
      name: 'opacity',
      title: 'Opacity fade',
      description: 'Fades inactive slides slightly.',
      type: 'boolean',
      initialValue: false,
    }),
    defineField({
      name: 'columns',
      title: 'Desktop columns',
      description: 'Fallback grid hint and default slide size.',
      type: 'number',
      initialValue: 2,
      options: {
        list: [
          {title: '2 columns', value: 2},
          {title: '3 columns', value: 3},
        ],
      },
    }),
  ],
  preview: {
    select: {
      title: 'caption',
      images: 'images',
    },
    prepare({title, images}) {
      const count = Array.isArray(images) ? images.length : 0
      return {
        title: title || 'Image carousel',
        subtitle: `${count} image${count === 1 ? '' : 's'}`,
      }
    },
  },
})
