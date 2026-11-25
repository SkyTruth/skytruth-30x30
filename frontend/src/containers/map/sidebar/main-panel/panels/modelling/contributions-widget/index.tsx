import { useAtomValue } from 'jotai';
import { useTranslations } from 'next-intl';

import { Accordion } from '@/components/ui/accordion';
import Widget from '@/components/widget';
import { drawStateAtom, modellingAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useLocationName from '@/hooks/use-location-name';
import { FCWithMessages } from '@/types';

import ContributionLocation from './location';
import ContributionSection from './section';
import useCoverageContributions from './use-coverage-contributions';

// TODO: TECH-3876, clean up the use_cb_api feature flag so this is the only stats panel
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

  const { countries, global, isLoading } = useCoverageContributions();
  const hasLocations = countries.length > 0;
  const firstCode = countries[0]?.code ?? '';

  const loading = modellingStatus === 'running' || drawStatus === 'uploading' || isLoading;
  const error = modellingStatus === 'error';
  const loadingMessage =
    drawStatus === 'uploading' ? t('uploading-layer-to-map') : t('loading-data');

  return (
    <Widget
      className="border-black py-0"
      noData={!hasLocations}
      loading={loading}
      loadingMessage={loadingMessage}
      error={error}
      errorMessage={errorMessage}
    >
      <Accordion key={firstCode} type="single" collapsible defaultValue={firstCode}>
        {hasLocations && (
          <ContributionSection title={t('national-level-section')}>
            {countries.map((stats) => (
              <ContributionLocation
                key={stats.code}
                title={getLocationName(stats.location)}
                stats={stats}
              />
            ))}
          </ContributionSection>
        )}
        {global && (
          <ContributionSection title={t('global-section')}>
            <ContributionLocation title={t('globe')} stats={global} />
          </ContributionSection>
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
  ...ContributionLocation.messages,
];

export default ContributionsWidget;
