import { ComponentProps } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import HabitatContributionChart from '@/components/charts/habitat-contribution-chart';
import HabitatContributionList from '@/components/charts/habitat-contribution-chart/list';
import TooltipButton from '@/components/tooltip-button';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

import type { StatStatus } from '../helpers';
import LegendItem from '../legend/item';
import StatStatusMessage from '../stat-status-message';
import type { HabitatContribution } from '../use-habitat-contributions';

export type HabitatProtectionProps = {
  className?: string;
  status: StatStatus;
  rows: HabitatContribution[];
  tooltip?: ComponentProps<typeof TooltipButton>;
  // Terrestrial habitats come from one request, so only "Calculating habitat protection..."
  // shows until they all arrive
  loadsAtOnce?: boolean;
};

const HabitatProtection: FCWithMessages<HabitatProtectionProps> = ({
  className,
  status,
  rows,
  tooltip,
  loadsAtOnce = false,
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const addedRows = rows.filter(
    ({ status, contribution }) => status === 'success' && contribution?.added > 0
  );
  const loadingNames = rows
    .filter(({ status }) => status === 'loading')
    .map(({ name }) => name.toLocaleLowerCase(locale));
  const isLoading = loadingNames.length > 0;
  const hasError = rows.some(({ status }) => status === 'error');

  if (!addedRows.length && status !== 'error' && (isLoading || !hasError)) {
    return loadsAtOnce && (isLoading || status === 'loading') ? (
      <p aria-live="polite" className={cn('text-xs', className)}>
        {t('calculating-habitat-protection')}
      </p>
    ) : null;
  }

  return (
    <div className={className}>
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-base font-bold">{t('habitat-protection')}</h4>
        {tooltip && <TooltipButton side="right" {...tooltip} />}
      </div>
      <StatStatusMessage status={status} />
      {status === 'success' && (
        <>
          {addedRows.length > 0 && (
            <ul aria-hidden className="pt-3 font-mono text-xs">
              <LegendItem className="bg-blue-700">{t('newly-protected-habitat')}</LegendItem>
            </ul>
          )}
          {addedRows.length > 0 && (
            <HabitatContributionList className="pt-3">
              {addedRows.map(({ slug, name, color, contribution, tooltip }, index) => (
                <HabitatContributionChart
                  key={slug}
                  className={index === 0 ? 'pt-1' : 'pt-4'}
                  title={name}
                  color={color}
                  contribution={contribution}
                  tooltip={tooltip}
                />
              ))}
            </HabitatContributionList>
          )}
          <p aria-live="polite" className="pt-3 text-xs empty:pt-0">
            {isLoading &&
              t('still-calculating-habitats', {
                habitats: new Intl.ListFormat(locale, { type: 'conjunction' }).format(loadingNames),
              })}
            {!isLoading && hasError && t('habitat-data-error')}
          </p>
        </>
      )}
    </div>
  );
};

HabitatProtection.messages = [
  'containers.map-sidebar-main-panel',
  ...TooltipButton.messages,
  ...StatStatusMessage.messages,
  ...HabitatContributionList.messages,
  ...HabitatContributionChart.messages,
];

export default HabitatProtection;
