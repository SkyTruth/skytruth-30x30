import { useEffect, useRef } from 'react';

import { useRouter } from 'next/router';

import { BBox } from '@turf/turf';
import { useAtom } from 'jotai';
import { useLocale } from 'next-intl';

import { CustomMapProps } from '@/components/map/types';
import { bboxLocationAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { combineBoundingBoxes } from '@/lib/utils/geo';
import { useGetLocations } from '@/types/generated/location';
import { Location } from '@/types/generated/strapi.schemas';

export default function useMapLocationBounds() {
  const locale = useLocale();

  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const [, setBboxLocation] = useAtom(bboxLocationAtom);
  const [{ tab }] = useSyncMapContentSettings();

  const previousLocationCodeRef = useRef(locationCode);
  const pendingLocationChangeRef = useRef(false); // Waiting for data after a location change
  const tabWhenLocationChangedRef = useRef(tab);

  const { data, isFetching } = useGetLocations<Location>(
    {
      locale,
      // @ts-ignore
      fields: ['marine_bounds', 'terrestrial_bounds'],
      filters: {
        code: locationCode,
      },
    },
    {
      query: {
        placeholderData: { data: [] },
        select: ({ data }) => data[0]?.attributes ?? {},
      },
    }
  );

  useEffect(() => {
    const hasLocationChanged =
      locationCode !== previousLocationCodeRef.current && !!previousLocationCodeRef.current;
    const isDataReady = !isFetching && data;

    if (hasLocationChanged) {
      pendingLocationChangeRef.current = true;
      tabWhenLocationChangedRef.current = tab;
    }

    if (pendingLocationChangeRef.current && isDataReady) {
      pendingLocationChangeRef.current = false;

      const { terrestrial_bounds, marine_bounds } = data;

      let locationBounds: CustomMapProps['bounds']['bbox'] = null;

      if (tab === 'terrestrial') {
        locationBounds = terrestrial_bounds as CustomMapProps['bounds']['bbox'];
      } else if (tab === 'marine') {
        locationBounds = marine_bounds as CustomMapProps['bounds']['bbox'];
      } else if (terrestrial_bounds || marine_bounds) {
        locationBounds = combineBoundingBoxes(
          // Falling back to the marine bounds because some locations don't have terrestrial bounds
          // e.g. ABJN and Gibraltar
          (terrestrial_bounds ?? marine_bounds) as BBox,
          // Falling back to the terrestrial bounds because some locations don't have marine bounds
          // e.g. any country without coast
          (marine_bounds ?? terrestrial_bounds) as BBox
        ) as CustomMapProps['bounds']['bbox'];
      }

      if (locationBounds !== null) {
        setBboxLocation(locationBounds);
      }
    }

    previousLocationCodeRef.current = locationCode;
  }, [locationCode, data, isFetching, tab, setBboxLocation]);
}
