import { ComponentProps, useCallback } from 'react';

import { useTranslations } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useSyncMapSettings } from '@/containers/map/content/map/sync-settings';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useDatasetsByEnvironment from '@/hooks/use-datasets-by-environment';
import { FCWithMessages } from '@/types';

import LayersGroup, { SWITCH_LABEL_CLASSES } from './layers-group';

const LayersPanel: FCWithMessages = (): JSX.Element => {
  const t = useTranslations('containers.map-sidebar-layers-panel');
  const [{ labels }, setMapSettings] = useSyncMapSettings();
  const [{ tab }] = useSyncMapContentSettings();

  const [datasets, { isLoading }] = useDatasetsByEnvironment();

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
      <LayersGroup
        name={t('basemap')}
        datasets={datasets.basemap}
        isOpen={['summary'].includes(tab)}
        loading={isLoading}
        showDatasetsNames={false}
        showBottomBorder={false}
        extraActiveLayers={labels ? 1 : 0}
      >
        {/*
          The labels toggle doesn't come from the basemap dataset and has slightly functionality implemented.
          Not ideal, but given it's a one-off, we'll pass the entry as a child to be displayed alongside the
          other entries, much like in the previous implementation.
        */}
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
