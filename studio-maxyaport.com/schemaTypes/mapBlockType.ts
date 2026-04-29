import {defineArrayMember, defineField, defineType} from 'sanity'

export const mapBlockType = defineType({
  name: 'mapBlock',
  title: 'Map',
  type: 'object',
  fields: [
    defineField({
      name: 'title',
      title: 'Title',
      type: 'string',
    }),
    defineField({
      name: 'caption',
      title: 'Caption',
      type: 'string',
    }),
    defineField({
      name: 'gpxFile',
      title: 'GPX file',
      description: 'Upload a GPX file to draw the route and elevation profile.',
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
      name: 'showElevation',
      title: 'Show elevation profile',
      type: 'boolean',
      initialValue: true,
    }),
    defineField({
      name: 'animation',
      title: 'Scroll animation',
      type: 'string',
      initialValue: 'draw',
      options: {
        list: [
          {title: 'Draw route', value: 'draw'},
          {title: 'Moving marker', value: 'marker'},
          {title: 'Fast tunnel vision', value: 'fast'},
          {title: 'Static', value: 'static'},
        ],
      },
    }),
    defineField({
      name: 'height',
      title: 'Card height',
      type: 'string',
      initialValue: 'standard',
      options: {
        list: [
          {title: 'Compact', value: 'compact'},
          {title: 'Standard', value: 'standard'},
          {title: 'Tall', value: 'tall'},
        ],
      },
    }),
    defineField({
      name: 'center',
      title: 'Map center',
      type: 'object',
      fields: [
        defineField({
          name: 'lat',
          title: 'Latitude',
          type: 'number',
          validation: (rule) => rule.required().min(-90).max(90),
        }),
        defineField({
          name: 'lng',
          title: 'Longitude',
          type: 'number',
          validation: (rule) => rule.required().min(-180).max(180),
        }),
      ],
    }),
    defineField({
      name: 'zoom',
      title: 'Zoom',
      type: 'number',
      initialValue: 9,
      validation: (rule) => rule.min(0).max(18),
    }),
    defineField({
      name: 'markers',
      title: 'Markers',
      type: 'array',
      of: [
        defineArrayMember({
          type: 'object',
          fields: [
            defineField({
              name: 'label',
              title: 'Label',
              type: 'string',
            }),
            defineField({
              name: 'lat',
              title: 'Latitude',
              type: 'number',
              validation: (rule) => rule.required().min(-90).max(90),
            }),
            defineField({
              name: 'lng',
              title: 'Longitude',
              type: 'number',
              validation: (rule) => rule.required().min(-180).max(180),
            }),
          ],
          preview: {
            select: {
              title: 'label',
              lat: 'lat',
              lng: 'lng',
            },
            prepare({title, lat, lng}) {
              return {
                title: title || 'Marker',
                subtitle: [lat, lng].filter((value) => value !== undefined).join(', '),
              }
            },
          },
        }),
      ],
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
  ],
  preview: {
    select: {
      title: 'title',
      caption: 'caption',
    },
    prepare({title, caption}) {
      return {
        title: title || 'Map',
        subtitle: caption,
      }
    },
  },
})
