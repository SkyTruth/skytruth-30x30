/**
 * aggregated-stats service
 * */
import { AggregatedStats } from '../controllers/aggregated-stat';

type AggregatedStatsParams = {
    locations: string[],
    apiNamespace: string,
    locale?: string,
    environment?: string, 
    year?: number,
    subFieldName?: string,
    subFieldValue?: string
  }


export default () => ({
  async getAggregatedStats({
    locations,
    apiNamespace,
    locale,
    environment = null, 
    year = null,
    subFieldName = null,
    subFieldValue = null
  }: AggregatedStatsParams): Promise<AggregatedStats[]> {
     const stats = await strapi.db.query(apiNamespace).findMany({
      where: {
        location: {
          code: {
            $in: locations
          }
        },
        ...(year ? { year } : {}),
        ...(environment ? { environment: { slug: environment } } : {}),
        ...(subFieldName && subFieldValue ? {
          [subFieldName]: {
              slug: subFieldValue,
          },
        } : {})
      },
      populate: {
        location: true,
        environment: true,
          [subFieldName]: {
          populate: {
            localizations: {
          filters: { locale },
          fields: ['id', 'slug', 'locale']
      }
          }
        },
      },
      ...(year ? { orderBy: { year: 'asc' }} : {})
    })

      const aggregatedStats = stats.reduce<Record<string, AggregatedStats>>((acc, stat) => {
        const location = stat.location.code;
        const hasSharedMarineArea = stat.location.has_shared_marine_area;
        const environment = stat?.environment?.slug;
        const year = stat?.year;
        const sub = {
          slug: stat[subFieldName]?.slug,
          name: stat[subFieldName]?.localizations[0]?.name ?? stat[subFieldName]?.name
        };

        // Some tables call protected area protected_area, others call it area
        const protected_area = stat?.protected_area ?? stat?.area 
        let totalArea = +stat.total_area;

        if (!totalArea) {
          totalArea = 
            environment === 'terrestrial' 
            ? +stat.location.total_terrestrial_area : +stat.location.total_marine_area 

        }

        const recordKey = `${year ?? ''}-${environment ?? ''}-${sub.slug ?? ''}`
        if (!acc[recordKey]) {
          acc[recordKey] = {
            year,
            environment,
            ...(subFieldName ? { [subFieldName]: sub } : {}),
            total_area: 0,
            protected_area: 0,
            locations: [],
            hasSharedMarineArea: false,
            coverage: 0,
            updatedAt: null
          };
        }

        acc[recordKey].total_area += totalArea;
        acc[recordKey].protected_area += protected_area;
        acc[recordKey].coverage = 
        (acc[recordKey].protected_area / acc[recordKey].total_area) * 100;
        acc[recordKey].locations.push(location);
        acc[recordKey].hasSharedMarineArea ||= hasSharedMarineArea;
        acc[recordKey].updatedAt = 
          acc[recordKey].updatedAt && new Date(acc[recordKey].updatedAt) > new Date(stat.updatedAt)
           ? acc[recordKey].updatedAt : stat.updatedAt

        return acc;
    }, {});
      
    const sortedStats = Object.values(aggregatedStats).sort((a,b) => a.year - b.year);
      
    return sortedStats;
  }
});
