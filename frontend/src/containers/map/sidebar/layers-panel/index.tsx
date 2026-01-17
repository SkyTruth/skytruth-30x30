import { ComponentProps, useCallback } from 'react';

import { useAtom } from 'jotai';
import { useTranslations } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useSyncMapSettings } from '@/containers/map/content/map/sync-settings';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useDatasetsByEnvironment from '@/hooks/use-datasets-by-environment';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import { FCWithMessages } from '@/types';
import { MapTypes } from '@/types/map';

import { mapTypeAtom } from '../../store';

import { SWITCH_LABEL_CLASSES } from './constants';
import CustomLayersGroup from './custom-layers-group';
import LayersGroup from './layers-group';

const LayersPanel: FCWithMessages = (): JSX.Element => {
  const t = useTranslations('containers.map-sidebar-layers-panel');
  const [{ labels }, setMapSettings] = useSyncMapSettings();
  const [{ tab }] = useSyncMapContentSettings();

  const [datasets, { isLoading }] = useDatasetsByEnvironment();

  const [mapType] = useAtom(mapTypeAtom);

  const isCustomLayersActive = useFeatureFlag('is_custom_layers_active');

  const handleLabelsChange = useCallback(
    (active: Parameters<ComponentProps<typeof Switch>['onCheckedChange']>[0]) => {
      setMapSettings((prev) => ({
        ...prev,
        labels: active,
      }));
    },
    [setMapSettings]
  );

  return (
    <div className="h-full overflow-auto px-4 text-xs">
      <div className="py-1">
        <h3 className="text-xl font-extrabold">{t('map-layers')}</h3>
      </div>
      <LayersGroup
        name={t('terrestrial-data')}
        datasets={datasets.terrestrial}
        isOpen={['summary', 'terrestrial'].includes(tab)}
        loading={isLoading}
      />
      <LayersGroup
        name={t('marine-data')}
        datasets={datasets.marine}
        isOpen={['summary', 'marine'].includes(tab)}
        loading={isLoading}
      />
      {/*
          The labels and custom layers toggles don't come from the datasets in the database and have slightly 
          different functionality. It's not an ideal set up, but until custom layers are saved for accounts, 
          we'll pass the layer options as children to be displayed alongside the other entries, much like in the other
          implementations.
      */}

      {
        // TODO: TECH-3372 remove feature flag check
        mapType === MapTypes.ConservationBuilder && isCustomLayersActive ? (
          <CustomLayersGroup name="Custom Layers" isOpen={true} />
        ) : null
      }
      <LayersGroup
        name={t('basemap')}
        datasets={datasets.basemap}
        isOpen={['summary'].includes(tab)}
        loading={isLoading}
        showDatasetsNames={false}
        showBottomBorder={false}
        extraActiveLayers={labels ? 1 : 0}
      >
        <li className="flex items-start justify-between">
          <span className="flex items-start gap-2">
            <Switch
              id="labels-switch"
              className="mt-px"
              checked={labels}
              onCheckedChange={handleLabelsChange}
            />
            <Label htmlFor="labels-switch" className={SWITCH_LABEL_CLASSES}>
              {t('labels')}
            </Label>
          </span>
        </li>
      </LayersGroup>
    </div>
  );
};

LayersPanel.messages = ['containers.map-sidebar-layers-panel', ...TooltipButton.messages];

export default LayersPanel;
