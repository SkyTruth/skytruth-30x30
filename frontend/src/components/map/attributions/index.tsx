import { FC } from 'react';

import { AttributionControl } from 'react-map-gl';

import { useLocale } from 'next-intl';

import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { useGetLayers } from '@/types/generated/layer';

const Attributions: FC = () => {
  const locale = useLocale();
  const [activeLayers] = useSyncMapLayers();

  const layerQuery = useGetLayers(
    {
      locale,
      filters: {
        slug: {
          $in: activeLayers,
        },
      },
      populate: 'metadata',
    },
    {
      query: {
        enabled: !!activeLayers.length,
        select: ({ data }) =>
          data.map(({ attributes: { metadata } }) => metadata?.source).filter((source) => !!source),
      },
    }
  );

  return (
    <AttributionControl
      key={layerQuery.data?.join('')}
      compact={false}
      customAttribution={layerQuery.data}
    />
  );
};

export default Attributions;
