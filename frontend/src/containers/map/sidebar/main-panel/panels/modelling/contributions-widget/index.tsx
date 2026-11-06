import { useEffect, useState } from 'react';

import { useAtomValue } from 'jotai';
import { useTranslations } from 'next-intl';

import { Accordion } from '@/components/ui/accordion';
import Widget from '@/components/widget';
import { drawStateAtom, modellingAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useLocationName from '@/hooks/use-location-name';
import { FCWithMessages } from '@/types';

import useTooltips from '../useTooltips';

import ContributionSection from './contribution-section';
import useCoverageContributions from './use-coverage-contributions';

/**
 * Stats in the Conservation Builder panel once a shape is drawn or uploaded: the
 * "National level contribution" and "Global level contribution" sections, each a list of
 * collapsible locations. Also shows the loading, error and no-data states
 *
 * Shown while the use_cb_api flag is on; the legacy `../widget` is shown while it is off
 * TODO: TECH-3876, clean up the use_cb_api feature flag so this is the only
 * stats panel
 */
const ContributionsWidget: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const tUploads = useTranslations('services.uploads');
  const getLocationName = useLocationName();

  const [{ tab }] = useSyncMapContentSettings();

  const { status: modellingStatus, errorMessage: errorMessageKey } = useAtomValue(modellingAtom);
  const { status: drawStatus } = useAtomValue(drawStateAtom);

  const errorMessage = errorMessageKey
    ? tUploads(errorMessageKey as Parameters<typeof tUploads>[0], { environment: tab })
    : undefined;

  const tooltips = useTooltips();

  const { national, global, isLoading } = useCoverageContributions();

  // One location is open, all others collapsed (starting with the first national one)
  const [openCode, setOpenCode] = useState('');
  const firstCode = national[0]?.code ?? '';
  useEffect(() => setOpenCode(firstCode), [firstCode]);

  const loading = modellingStatus === 'running' || drawStatus === 'uploading' || isLoading;
  const error = modellingStatus === 'error';
  const loadingMessage =
    drawStatus === 'uploading' ? t('uploading-layer-to-map') : t('loading-data');

  return (
    <Widget
      className="border-black py-0"
      noData={!national.length}
      loading={loading}
      loadingMessage={loadingMessage}
      error={error}
      errorMessage={errorMessage}
    >
      <Accordion type="single" collapsible value={openCode} onValueChange={setOpenCode}>
        <ContributionSection
          title={t('national-level-contribution')}
          tooltip={tooltips?.['contributionDetails']}
          items={national.map((stats) => ({ title: getLocationName(stats.location), stats }))}
        />
        {global && (
          <ContributionSection
            title={t('global-contribution')}
            tooltip={tooltips?.['globalContribution']}
            items={[{ title: t('globe'), stats: global }]}
          />
        )}
      </Accordion>
    </Widget>
  );
};

ContributionsWidget.messages = [
  'containers.map-sidebar-main-panel',
  'services.uploads',
  'locations',
  ...Widget.messages,
  ...ContributionSection.messages,
];

export default ContributionsWidget;
