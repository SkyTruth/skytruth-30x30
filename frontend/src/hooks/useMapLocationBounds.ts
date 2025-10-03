import { useEffect, useRef } from 'react';

import { useRouter } from 'next/router';

import { BBox } from '@turf/turf';
import { useAtom } from 'jotai';
import { useLocale } from 'next-intl';

import { CustomMapProps } from '@/components/map/types';
import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import { useSyncCustomRegion } from '@/containers/map/content/map/sync-settings';
import { bboxLocationAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { combineBoundingBoxes } from '@/lib/utils/geo';
import { useGetLocations } from '@/types/generated/location';
import { LocationListResponseDataItem } from '@/types/generated/strapi.schemas';

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

  const [customRegionLocations] = useSyncCustomRegion();

  const locationCodes =
    locationCode === CUSTOM_REGION_CODE ? [...customRegionLocations] : [locationCode];

  const { data, isFetching } = useGetLocations<Array<LocationListResponseDataItem>>(
    {
      locale,
      // @ts-ignore
      fields: ['marine_bounds', 'terrestrial_bounds'],
      filters: {
        code: {
          $in: locationCodes,
        },
      },
    },
    {
      query: {
        placeholderData: { data: [] },
        select: ({ data }) => data,
      },
    }
  );

  useEffect(() => {
    const hasLocationChanged =
      locationCode !== previousLocationCodeRef.current && !!previousLocationCodeRef.current;
    const isDataReady = !isFetching && data?.length;

    if (hasLocationChanged) {
      pendingLocationChangeRef.current = true;
      tabWhenLocationChangedRef.current = tab;
    }

    if (pendingLocationChangeRef.current && isDataReady) {
      pendingLocationChangeRef.current = false;

      const bounds: BBox[] = data.reduce((acc, loc) => {
        const {
          attributes: { marine_bounds = null, terrestrial_bounds = null },
        } = loc;
        switch (tab) {
          case 'marine':
            if (marine_bounds) {
              acc.push(marine_bounds);
            }
            return acc;
          case 'terrestrial':
            if (terrestrial_bounds) {
              acc.push(terrestrial_bounds);
            }
            return acc;
          case 'summary':
            if (marine_bounds) {
              acc.push(marine_bounds);
            }
            if (terrestrial_bounds) {
              acc.push(terrestrial_bounds);
            }

            return acc;
        }
        return acc;
      }, []);

      const unionBounds = combineBoundingBoxes(bounds) as CustomMapProps['bounds']['bbox'];

      if (unionBounds !== null) {
        setBboxLocation(unionBounds);
      }
    }

    previousLocationCodeRef.current = locationCode;
  }, [locationCode, data, isFetching, tab, setBboxLocation]);
}
