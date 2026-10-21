import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useMap } from 'react-map-gl';

import { useAtomValue } from 'jotai';
import { useLocale } from 'next-intl';

import { layersInteractiveAtom, layersInteractiveIdsAtom, popupAtom } from '@/containers/map/store';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import useLocationName from '@/hooks/use-location-name';
import { useGetLayers } from '@/types/generated/layer';
import { useGetMpaaEstablishmentStages } from '@/types/generated/mpaa-establishment-stage';
import { useGetMpaaProtectionLevels } from '@/types/generated/mpaa-protection-level';
import { useGetPas } from '@/types/generated/pa';
import { Pa } from '@/types/generated/strapi.schemas';
import { LayerTyped } from '@/types/layers';

import { MergedPa, mergeProtectedAreas } from './merge-PAs';
import { ClickedPa, clickedPaKey, readClickedPa } from './parse-tile-click';

/** The protected areas under the click point, across every protected-area layer. */
export const useClickedProtectedAreas = (): ClickedPa[] => {
  const locale = useLocale();
  const { default: map } = useMap();
  const popup = useAtomValue(popupAtom);
  const layersInteractive = useAtomValue(layersInteractiveAtom);
  const layersInteractiveIds = useAtomValue(layersInteractiveIdsAtom);

  const [rendered, setRendered] = useState(false);
  const lastClicked = useRef<ClickedPa[]>([]);

  const sourcesQuery = useGetLayers<string[]>(
    {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      locale,
      filters: {
        slug: {
          $in: layersInteractive,
        },
      },
    },
    {
      query: {
        enabled: layersInteractive.length > 0,
        select: ({ data }) =>
          (data as LayerTyped[])
            .filter(
              (layer) =>
                layer.interaction_config?.['@@type'] === 'ProtectedAreaPopup' &&
                layer.config?.source?.type === 'vector'
            )
            .map((layer) => layer.config.source.id),
      },
    }
  );

  const handleMapRender = useCallback(() => {
    setRendered(map?.loaded() && map?.areTilesLoaded());
  }, [map]);

  useEffect(() => {
    map?.on('render', handleMapRender);

    setRendered(map?.loaded() && map?.areTilesLoaded());

    return () => {
      map?.off('render', handleMapRender);
    };
  }, [map, handleMapRender]);

  return useMemo(() => {
    const sources = sourcesQuery.data;

    if (sources?.length && rendered && popup && map) {
      const point = map.project(popup.lngLat);

      // check if the point is outside the canvas
      if (
        point.x < 0 ||
        point.x > map.getCanvas().width ||
        point.y < 0 ||
        point.y > map.getCanvas().height
      ) {
        return lastClicked.current;
      }
      const query = map.queryRenderedFeatures(point, {
        layers: layersInteractiveIds,
      });

      // The same parcel can appear under several layers and across tile boundaries.
      const seen = new Set<string>();
      const features = query
        .filter((feature) => sources.includes(feature.source))
        .map((feature) => readClickedPa(feature.properties))
        .filter((clicked) => {
          const key = clickedPaKey(clicked);
          if (!key || seen.has(key)) return false;
          seen.add(key);
          return true;
        });

      if (features.length) {
        lastClicked.current = features;
      }
    }

    return lastClicked.current;
  }, [popup, sourcesQuery.data, layersInteractiveIds, map, rendered]);
};

/** The `/pas` rows for the clicked parcels, sites without a parcel id, and zones. */
export const useProtectedAreaRecords = (clicked: ClickedPa[]) => {
  const filters = useMemo(() => {
    const parcelIds = clicked.map((pa) => pa.wdpaPId).filter(Boolean);
    const siteIds = clicked
      .filter((pa) => !pa.wdpaPId)
      .map((pa) => pa.wdpaid)
      .filter(Boolean);
    const zoneIds = clicked.map((pa) => pa.zoneId).filter(Boolean);

    return {
      $or: [
        parcelIds.length > 0 && { wdpa_p_id: { $in: parcelIds } },
        siteIds.length > 0 && { wdpaid: { $in: siteIds } },
        zoneIds.length > 0 && { zone_id: { $in: zoneIds } },
      ].filter(Boolean),
    };
  }, [clicked]);

  const { data: rows, isFetching } = useGetPas<Pa[]>(
    {
      // @ts-ignore
      fields: ['name', 'area', 'wdpaid', 'wdpa_p_id', 'zone_id'],
      // @ts-ignore
      populate: {
        protection_status: {
          fields: ['slug', 'name', 'locale'],
          populate: { localizations: { fields: ['slug', 'name', 'locale'] } },
        },
        mpaa_protection_level: {
          fields: ['slug', 'name', 'locale'],
          populate: { localizations: { fields: ['slug', 'name', 'locale'] } },
        },
        mpaa_establishment_stage: {
          fields: ['slug', 'name', 'locale'],
          populate: { localizations: { fields: ['slug', 'name', 'locale'] } },
        },
        iucn_category: {
          fields: ['slug', 'name', 'locale'],
          populate: { localizations: { fields: ['slug', 'name', 'locale'] } },
        },
        data_source: { fields: ['slug'] },
        environment: { fields: ['slug'] },
        location: { fields: ['code', 'type'] },
      },
      filters,
      'pagination[pageSize]': 100,
    },
    {
      query: {
        enabled: clicked.length > 0,
        select: ({ data }) => data,
      },
    }
  );

  return { rows, isFetching };
};

/** One card's worth of data per parcel, with MPAtlas-only zones built from the tile. */
export const useMergedProtectedAreas = (
  clicked: ClickedPa[],
  rows: Pa[] | undefined
): MergedPa[] => {
  const locale = useLocale();
  const getLocationName = useLocationName();
  const isIhoActive = useFeatureFlag('is_iho_active');

  const { data: protectionLevelNames } = useGetMpaaProtectionLevels<Record<string, string>>(
    {
      locale,
      // @ts-ignore
      fields: ['name', 'slug'],
    },
    {
      query: {
        select: ({ data }) => Object.fromEntries(data.map((level) => [level.slug, level.name])),
        placeholderData: { data: [] },
      },
    }
  );

  const { data: establishmentStageNames } = useGetMpaaEstablishmentStages<Record<string, string>>(
    {
      locale,
      // @ts-ignore
      fields: ['name', 'slug'],
    },
    {
      query: {
        select: ({ data }) => Object.fromEntries(data.map((stage) => [stage.slug, stage.name])),
        placeholderData: { data: [] },
      },
    }
  );

  return useMemo(
    () =>
      mergeProtectedAreas(rows ?? [], clicked, {
        locale,
        getLocationName,
        isIhoActive: Boolean(isIhoActive),
        protectionLevelNames,
        establishmentStageNames,
      }),
    [
      rows,
      clicked,
      locale,
      getLocationName,
      isIhoActive,
      protectionLevelNames,
      establishmentStageNames,
    ]
  );
};
