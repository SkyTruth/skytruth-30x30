import { useMemo } from 'react';

import { useLocale } from 'next-intl';

import { ENVIRONMENTS } from '@/constants/environments';
import { useGetDatasets } from '@/types/generated/dataset';
import { Dataset } from '@/types/generated/strapi.schemas';

export default function useDatasetsByEnvironment() {
  const locale = useLocale();

  const { data, isFetching } = useGetDatasets<Dataset[]>(
    {
      locale,
      sort: 'name:asc',
      // @ts-ignore
      populate: {
        layers: {
          populate: {
            metadata: true,
            environment: true,
          },
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
    const basemapDataset = data?.filter(dataset => dataset?.slug === 'basemap');
    const nonBasemapDatasets = data?.filter(dataset => dataset?.slug !== 'basemap');

    // A dataset can contain layers with different environments assigned, we want
    // to pick only the layers for the environment we're displaying.
    const filterLayersByEnvironment = (layers, environment) => {
      return (
        layers?.filter((item) => {
          return item.environment?.slug === environment;
        }) || []
      );
    };

    const parseDatasetsByEnvironment = (datasets: Dataset[], environment: string) => {
      const parsedDatasets = datasets?.map((d) => {
        const { layers, ...rest } = d;
        const filteredLayers = filterLayersByEnvironment(layers, environment);

        // If dataset contains no layers, it should not displayed. We'll filter this
        // values before the return of the parsed data array.
        if (!filteredLayers.length) return null;

        return {
          documentId: d?.documentId,
          ...rest,
          layers: filteredLayers,
        } as Dataset;
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
  }, [data]);

  return [datasets, { isLoading: isFetching }] as const;
}
