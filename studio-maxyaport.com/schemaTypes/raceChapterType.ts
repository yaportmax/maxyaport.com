import {defineArrayMember, defineField, defineType} from 'sanity'

const animationOptions = [
  {title: 'Draw route', value: 'draw'},
  {title: 'Moving marker', value: 'marker'},
  {title: 'Fast tunnel vision', value: 'fast'},
  {title: 'Finish calm', value: 'finish'},
]

export const raceChapterType = defineType({
  name: 'raceChapter',
  title: 'Race chapter',
  type: 'object',
  fields: [
    defineField({
      name: 'title',
      title: 'Chapter title',
      type: 'string',
      validation: (rule) => rule.required(),
    }),
    defineField({
      name: 'body',
      title: 'Text',
      type: 'array',
      of: [
        defineArrayMember({
          type: 'block',
          styles: [
            {title: 'Normal', value: 'normal'},
            {title: 'Heading 3', value: 'h3'},
            {title: 'Quote', value: 'blockquote'},
          ],
          lists: [
            {title: 'Bullet', value: 'bullet'},
            {title: 'Numbered', value: 'number'},
          ],
          marks: {
            decorators: [
              {title: 'Strong', value: 'strong'},
              {title: 'Emphasis', value: 'em'},
              {title: 'Code', value: 'code'},
            ],
            annotations: [
              defineArrayMember({
                name: 'link',
                title: 'Link',
                type: 'object',
                fields: [
                  defineField({
                    name: 'href',
                    title: 'URL',
                    type: 'url',
                    validation: (rule) => rule.required(),
                  }),
                ],
              }),
            ],
          },
        }),
      ],
    }),
    defineField({
      name: 'mileStart',
      title: 'Mile start',
      type: 'number',
      validation: (rule) => rule.min(0),
    }),
    defineField({
      name: 'mileEnd',
      title: 'Mile end',
      type: 'number',
      validation: (rule) => rule.min(0),
    }),
    defineField({
      name: 'gpxFile',
      title: 'GPX file',
      description: 'Upload a GPX for this segment. If omitted, paste a GPX URL below.',
      type: 'file',
      options: {
        accept: '.gpx,application/gpx+xml,text/xml,application/xml',
      },
    }),
    defineField({
      name: 'gpxUrl',
      title: 'GPX URL',
      description: 'Optional public GPX URL, for example /routes/canyons-2026.gpx.',
      type: 'string',
    }),
    defineField({
      name: 'mapAnimation',
      title: 'Map animation',
      type: 'string',
      initialValue: 'draw',
      options: {list: animationOptions},
    }),
    defineField({
      name: 'mood',
      title: 'Mood',
      type: 'string',
      options: {
        list: [
          {title: 'Neutral', value: 'neutral'},
          {title: 'Cold start', value: 'cold'},
          {title: 'Good', value: 'good'},
          {title: 'Hard', value: 'hard'},
          {title: 'Weird good part', value: 'weird-good'},
          {title: 'Finish', value: 'finish'},
        ],
      },
      initialValue: 'neutral',
    }),
    defineField({
      name: 'callout',
      title: 'Callout',
      type: 'string',
    }),
    defineField({
      name: 'routeLabels',
      title: 'Route labels by mile',
      description: 'Labels that fade in on the route line, useful for aid stations.',
      type: 'array',
      of: [
        defineArrayMember({
          type: 'object',
          fields: [
            defineField({
              name: 'label',
              title: 'Label',
              type: 'string',
              validation: (rule) => rule.required(),
            }),
            defineField({
              name: 'mile',
              title: 'Mile',
              type: 'number',
              validation: (rule) => rule.required().min(0),
            }),
          ],
          preview: {
            select: {
              title: 'label',
              mile: 'mile',
            },
            prepare({title, mile}) {
              return {
                title: title || 'Route label',
                subtitle: typeof mile === 'number' ? `Mile ${mile}` : undefined,
              }
            },
          },
        }),
      ],
    }),
    defineField({
      name: 'photos',
      title: 'Photos',
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
              title: 'Caption',
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
                title: title || 'Chapter photo',
                media,
              }
            },
          },
        }),
      ],
    }),
    defineField({
      name: 'photoCaption',
      title: 'Photo carousel caption',
      type: 'string',
    }),
    defineField({
      name: 'carouselLoop',
      title: 'Photo carousel loop',
      type: 'boolean',
      initialValue: false,
    }),
    defineField({
      name: 'carouselAutoplay',
      title: 'Photo carousel autoplay',
      type: 'boolean',
      initialValue: false,
    }),
    defineField({
      name: 'carouselAutoplayDelay',
      title: 'Autoplay delay',
      type: 'number',
      initialValue: 4200,
      hidden: ({parent}) => !parent?.carouselAutoplay,
      validation: (rule) => rule.min(1200).max(15000),
    }),
    defineField({
      name: 'carouselVariableWidths',
      title: 'Variable photo widths',
      type: 'boolean',
      initialValue: true,
    }),
    defineField({
      name: 'carouselDragFree',
      title: 'Drag free photo carousel',
      type: 'boolean',
      initialValue: false,
    }),
    defineField({
      name: 'carouselParallax',
      title: 'Photo parallax',
      type: 'boolean',
      initialValue: true,
    }),
    defineField({
      name: 'carouselOpacity',
      title: 'Photo opacity fade',
      type: 'boolean',
      initialValue: true,
    }),
    defineField({
      name: 'carouselColumns',
      title: 'Photo slide size',
      type: 'number',
      initialValue: 2,
      options: {
        list: [
          {title: 'Large slides', value: 2},
          {title: 'Smaller slides', value: 3},
        ],
      },
    }),
  ],
  preview: {
    select: {
      title: 'title',
      mileStart: 'mileStart',
      mileEnd: 'mileEnd',
      mood: 'mood',
    },
    prepare({title, mileStart, mileEnd, mood}) {
      const miles =
        typeof mileStart === 'number' && typeof mileEnd === 'number'
          ? `Miles ${mileStart}-${mileEnd}`
          : mood
      return {
        title: title || 'Race chapter',
        subtitle: miles,
      }
    },
  },
})
