export default {
  /**
   * An asynchronous register function that runs before
   * your application is initialized.
   *
   * This gives you an opportunity to extend code.
   */
  register({ strapi }) {
    if (strapi.plugin('documentation')) {
      const override = {
        // Limit this override to the version Orval reads
        info: { version: '1.0.0' },
        paths: {
          '/aggregated-stats': {
            get: {
              summary: 'Get aggregated statistics',
              tags: ['Aggregated-stats'],
              parameters: [
                { name: 'locations', in: 'query', required: true, schema: { type: 'string' } },
                { name: 'stats', in: 'query', required: false, schema: { type: 'string',
                  enum: ['protection_coverage','habitat','mpaa_protection_level','fishing_protection_level'],
                  default: 'protection_coverage' } },
                { name: 'year', in: 'query', required: false, schema: { type: 'integer', format: 'int32' } },
                { name: 'environment', in: 'query', required: false, schema: { type: 'string', nullable: true } },
                { name: 'habitat', in: 'query', required: false, schema: { type: 'string', nullable: true } },
                { name: 'fishing_protection_level', in: 'query', required: false, schema: { type: 'string', nullable: true } },
                { name: 'mpaa_protection_level', in: 'query', required: false, schema: { type: 'string', nullable: true } },
                { name: 'locale', in: 'query', required: false, schema: { type: 'string', nullable: true}}
              ],
              responses: {
                200: { description: 'OK', content: { 'application/json': { schema: { $ref: '#/components/schemas/AggregatedStatsEnvelope' } } } },
                400: { description: 'Bad Request', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } }
              },
              operationId: 'getAggregatedStats'
            }
          }
        },
        components: {
          schemas: {
            AggregatedStats: {
              type: 'object',
              required: ['coverage', 'protected_area', 'locations', 'total_area'],
              properties: {
                coverage: { type: 'number' },
                protected_area: { type: 'number' },
                locations: { type: 'array', items: { type: 'string' } },
                hasSharedMarineArea: { type: 'boolean' },
                total_area: { type: 'number' },
                environment: { type: 'string', nullable: true },
                fishing_protection_level: { type: 'object', nullable: true, properties: {
                  slug: { type: 'string' },
                  name: { type: 'string'}
                  }
                },
                mpaa_protection_level: { type: 'object', nullable: true, properties: {
                  slug: { type: 'string' },
                  name: { type: 'string'}
                  }
                },
                habitat: { type: 'object', nullable: true, properties: {
                  slug: { type: 'string' },
                  name: { type: 'string'}
                  }
                },
                year: { type: 'integer', format: 'int32', nullable: true },
                updatedAt: {type: 'string'}
              }
            },
            StatsResponse: {
              type: 'object',
              properties: {
                protection_coverage: { type: 'array', items: { $ref: '#/components/schemas/AggregatedStats' } },
                habitat: { type: 'array', items: { $ref: '#/components/schemas/AggregatedStats' } },
                mpaa_protection_level: { type: 'array', items: { $ref: '#/components/schemas/AggregatedStats' } },
                fishing_protection_level: { type: 'array', items: { $ref: '#/components/schemas/AggregatedStats' } }
              },
              additionalProperties: false
            },
            AggregatedStatsEnvelope: {
              type: 'object',
              required: ['data'],
              properties: { data: { $ref: '#/components/schemas/StatsResponse' } }
            },
            Error: {
              type: 'object',
              properties: {
                error: { type: 'string' },
                message: { type: 'string' },
                status: { type: 'integer' }
              }
            }
          }
        }
      };

      // Register the override with the plugin
      strapi
        .plugin('documentation')
        .service('override')
        .registerOverride(override);
    }
  },

  /**
   * An asynchronous bootstrap function that runs before
   * your application gets started.
   *
   * This gives you an opportunity to set up your data model,
   * run jobs, or perform some special logic.
   */
  bootstrap(/*{ strapi }*/) {},
};
