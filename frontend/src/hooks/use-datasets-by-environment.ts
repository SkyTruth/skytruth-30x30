import { useMemo } from 'react';

import { useLocale } from 'next-intl';

import { ENVIRONMENTS } from '@/constants/environments';
import { TERRITORY_LAYERS } from '@/constants/territories'; // TODO TECH-3174: Clean up
import { useGetDatasets } from '@/types/generated/dataset';
import { DatasetUpdatedByData } from '@/types/generated/strapi.schemas';

import { useFeatureFlag } from './use-feature-flag'; // TODO TECH-3174: Clean up

export default function useDatasetsByEnvironment() {
  const locale = useLocale();

  // TODO TECH-3174: Clean up
  const areTerritoriesActive = useFeatureFlag('are_territories_active');

  const { data, isFetching } = useGetDatasets<DatasetUpdatedByData[]>(
    {
      locale,
      sort: 'name:asc',
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        layers: {
          populate: 'metadata,environment',
        },
      },
    },
    {
      query: {
        select: ({ data }) => data,
      },
    }
  );

  // Break up datasets by terrestrial, marine, basemap for ease of handling
  const datasets = useMemo(() => {
    // Basemap dataset is displayed separately in the panel, much like terrestrial/maritime.
    // We need to split it out from the datasets we're processing in order to display this correctly.
    const basemapDataset = data?.filter(({ attributes }) => attributes?.slug === 'basemap');
    const basemapDatasetIds = basemapDataset?.map(({ id }) => id);
    const nonBasemapDatasets = data?.filter(({ id }) => !basemapDatasetIds.includes(id));

    // A dataset can contain layers with different environments assigned, we want
    // to pick only the layers for the environment we're displaying.
    const filterLayersByEnvironment = (layers, environment) => {
      const layersData = layers?.data;
      return (
        layersData?.filter(({ attributes }) => {
          // TODO TECH-3174: Clean up
          const layerUrl = attributes?.config?.source?.url;
          const layerSlug = attributes?.slug;

          const environmentData = attributes?.environment?.data;
          return (
            environmentData?.attributes?.slug === environment &&
            // TODO TECH-3174: Clean up
            ((!areTerritoriesActive &&
              (!TERRITORY_LAYERS[layerSlug] || TERRITORY_LAYERS[layerSlug] !== layerUrl)) ||
              (areTerritoriesActive &&
                (!TERRITORY_LAYERS[layerSlug] || TERRITORY_LAYERS[layerSlug] === layerUrl)))
          );
        }) || [areTerritoriesActive]
      );
    };

    const parseDatasetsByEnvironment = (datasets: DatasetUpdatedByData[], environment: string) => {
      const parsedDatasets = datasets?.map((d) => {
        const { layers, ...rest } = d?.attributes;
        const filteredLayers = filterLayersByEnvironment(layers, environment);

        // If dataset contains no layers, it should not displayed. We'll filter this
        // values before the return of the parsed data array.
        if (!filteredLayers.length) return null;

        return {
          id: d?.id,
          attributes: {
            ...rest,
            layers: {
              data: filteredLayers,
            },
          },
        } as DatasetUpdatedByData;
      });

      // Prevent displaying of groups when they are empty / contain no layers
      return parsedDatasets?.filter((dataset) => dataset !== null);
    };

    const [terrestrialDataset, marineDataset] = [
      ENVIRONMENTS.terrestrial,
      ENVIRONMENTS.marine,
    ]?.map((environment) => parseDatasetsByEnvironment(nonBasemapDatasets, environment));

    return {
      terrestrial: terrestrialDataset,
      marine: marineDataset,
      basemap: basemapDataset,
    };
  }, [data, areTerritoriesActive]);

  return [datasets, { isLoading: isFetching }] as const;
}
