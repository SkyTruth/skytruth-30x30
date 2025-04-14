// import { useEffect, useMemo } from 'react';

// import { usePreviousImmediate } from 'rooks';

// import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
// import { useSyncMapContentSettings } from '@/containers/map/sync-settings';

// import useDatasetsByEnvironment from './use-datasets-by-environment';

// export default function useMapDefaultLayers() {
//   const [, setMapLayers] = useSyncMapLayers();
//   const [{ tab }] = useSyncMapContentSettings();
//   const previousTab = usePreviousImmediate(tab);

//   const [datasets] = useDatasetsByEnvironment();

//   const defaultLayersIds = useMemo(() => {
//     const datasetsDefaultLayerIds = (datasets = []) => {
//       return datasets.reduce((acc, { attributes }) => {
//         const layersData = attributes?.layers?.data;
//         const defaultLayersIds = layersData.reduce(
//           (acc, { id, attributes }) => (attributes?.default ? [...acc, id] : acc),
//           []
//         );
//         return [...acc, ...defaultLayersIds];
//       }, []);
//     };

//     return {
//       terrestrial: datasetsDefaultLayerIds(datasets.terrestrial),
//       marine: datasetsDefaultLayerIds(datasets.marine),
//       basemap: datasetsDefaultLayerIds(datasets.basemap),
//     };
//   }, [datasets]);

//   useEffect(() => {
//     if (tab !== previousTab && !!previousTab) {
//       let mapLayers = [];
//       switch (tab) {
//         case 'summary':
//           mapLayers = ['terrestrial', 'marine', 'basemap']?.reduce(
//             (ids, dataset) => [...ids, ...defaultLayersIds[dataset]],
//             []
//           );
//           break;
//         case 'terrestrial':
//           mapLayers = defaultLayersIds.terrestrial;
//           break;
//         case 'marine':
//           mapLayers = defaultLayersIds.marine;
//           break;
//       }
//       setMapLayers(mapLayers);
//     }
//   }, [defaultLayersIds, setMapLayers, tab, previousTab]);
// }
