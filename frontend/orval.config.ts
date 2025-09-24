import { Config } from '@orval/core';

module.exports = {
  skytruth: {
    output: {
      mode: 'tags',
      client: 'react-query',
      target: './src/types/generated/strapi.ts',
      mock: false,
      clean: true,
      prettier: true,
      override: {
        mutator: {
          path: './src/services/api/index.ts',
          name: 'API',
        },
        query: {
          useQuery: true,
          useMutation: true,
          signal: true,
        },
        operations: {
          'get/data-tools': {
            query: {
              useInfinite: true,
              useInfiniteQueryParam: '"pagination[page]"',
            },
          },
        },
      },
    },
    input: {
      target: '../cms/src/extensions/documentation/documentation/1.0.0/full_documentation.json',
      filters: {
        tags: [
          'Aggregated-stats',
          'Location',
          'Habitat',
          'Habitat-stat',
          'Pa',
          'Mpaa-protection-level',
          'Mpaa-protection-level-stat',
          'Mpaa-establishment-stage',
          'Mpaa-establishment-stage-stat',
          'Mpa-protection-coverage-stat',
          'Mpaa-establishment-stage-status',
          'Mpa-iucn-category',
          'Protection-coverage-stat',
          'Protection-status',
          'Fishing-protection-level',
          'Fishing-protection-level-stat',
          'Dataset',
          'Layer',
          'Data-info',
          'Data-tool',
          'Data-tool-language',
          'Data-tool-resource-type',
          'Data-tool-ecosystem',
          'Data-source',
          'Static-indicator',
          'Contact-detail',
          'Environment',
          'Feature-flag'
        ],
      },
    },
  },
} satisfies Config;
