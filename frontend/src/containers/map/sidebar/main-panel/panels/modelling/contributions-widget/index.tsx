import { useEffect, useMemo, useState } from 'react';

import { useAtomValue } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import { Accordion } from '@/components/ui/accordion';
import Widget from '@/components/widget';
import { drawStateAtom, modellingAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useLocationName from '@/hooks/use-location-name';
import { FCWithMessages } from '@/types';
import { useGetDataInfos } from '@/types/generated/data-info';

import useTooltips from '../useTooltips';

import ContributionSection from './contribution-section';
import useCoverageContributions, { SectionStats } from './use-coverage-contributions';
import useFhpContributions from './use-fhp-contributions';

/**
 * Stats in the Conservation Builder panel once a shape is drawn or uploaded, grouped into
 * sections (e.g. "Countries", "Global"), each a list of collapsible locations. A section is
 * hidden if the shape doesn't intersect any of its locations. Also shows the loading, error
 * and no-data states
 *
 * Shown while the use_cb_api flag is on; the legacy `../widget` is shown while it is off
 * TODO: TECH-3876, clean up the use_cb_api feature flag so this is the only
 * stats panel
 */
const ContributionsWidget: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();
  const tUploads = useTranslations('services.uploads');
  const getLocationName = useLocationName();

  const [{ tab }] = useSyncMapContentSettings();

  const { status: modellingStatus, errorMessage: errorMessageKey } = useAtomValue(modellingAtom);
  const { status: drawStatus } = useAtomValue(drawStateAtom);

  const errorMessage = errorMessageKey
    ? tUploads(errorMessageKey as Parameters<typeof tUploads>[0], { environment: tab })
    : undefined;

  const tooltips = useTooltips();

  const { countries, regionsAndSeas, global, seaCodes, isLoading } = useCoverageContributions();
  const hasLocations = countries.length > 0 || regionsAndSeas.length > 0;

  // Fully/Highly Protected stats for every listed location, marine only
  const isMarine = tab === 'marine';
  const listedCodes = useMemo(
    () => [...countries, ...regionsAndSeas].map(({ code }) => code),
    [countries, regionsAndSeas]
  );
  const fhp = useFhpContributions(listedCodes, seaCodes, isMarine);
  // "Fully / Highly Protected" info tooltip with its linked source, from Strapi
  const { data: fhpTooltip } = useGetDataInfos(
    { locale, filters: { slug: 'cb-fully-highly-protected' }, populate: 'data_sources' },
    {
      query: {
        enabled: isMarine,
        select: ({ data }) =>
          data[0]
            ? {
                text: data[0].content,
                sources: data[0].data_sources?.map(({ documentId, slug, title, url }) => ({
                  documentId,
                  slug,
                  title,
                  url,
                })),
                sourcesLabel: t('fully-highly-protected-sources'),
              }
            : undefined,
      },
    }
  );
  const withMarineStats = (title: string, stats: SectionStats) => ({
    title,
    stats,
    ...(isMarine && {
      fhp: { status: fhp.status, contribution: fhp.byCode.get(stats.code), tooltip: fhpTooltip },
    }),
  });

  // One location is open, all others collapsed (starting with the first one listed)
  const [openCode, setOpenCode] = useState('');
  const firstCode = (countries[0] ?? regionsAndSeas[0])?.code ?? '';
  useEffect(() => setOpenCode(firstCode), [firstCode]);

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
      <Accordion type="single" collapsible value={openCode} onValueChange={setOpenCode}>
        {countries.length > 0 && (
          <ContributionSection
            title={t('countries-section')}
            tooltip={tooltips?.['countries']}
            items={countries.map((stats) =>
              withMarineStats(getLocationName(stats.location), stats)
            )}
          />
        )}
        {regionsAndSeas.length > 0 && (
          <ContributionSection
            title={t('regions-and-seas-section')}
            tooltip={tooltips?.['regionsAndSeas']}
            items={regionsAndSeas.map((stats) =>
              withMarineStats(getLocationName(stats.location), stats)
            )}
          />
        )}
        {global && (
          <ContributionSection
            title={t('global-section')}
            tooltip={tooltips?.['global']}
            items={[withMarineStats(t('globe'), global)]}
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
