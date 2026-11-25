import { ComponentProps, PropsWithChildren } from 'react';

import { ChevronDown } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';

import ContributionChart from '@/components/charts/contribution-chart';
import HabitatContributionChart from '@/components/charts/habitat-contribution-chart';
import HabitatContributionList from '@/components/charts/habitat-contribution-chart/list';
import TooltipButton from '@/components/tooltip-button';
import {
  AccordionContent,
  AccordionHeader,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { cn } from '@/lib/classnames';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

import type { StatStatus } from './stat-status';
import { SectionStats } from './use-coverage-contributions';
import useDataInfoTooltips from './use-data-info-tooltips';
import type { HabitatContribution } from './use-habitat-contributions';

// Strapi data-info entry for the coverage tooltip, shared with the Progress Tracker's
// coverage widgets
const COVERAGE_TOOLTIP_SLUG = 'coverage-widget';

/** One legend entry: a colored square with a black outline (`className` sets its color) and its label */
const LegendItem = ({ className, children }: PropsWithChildren<{ className: string }>) => (
  <li className="flex items-center gap-2">
    <span aria-hidden className={cn('h-2.5 w-2.5 border border-black', className)} />
    <span className="pt-[0.2em] leading-none">{children}</span>
  </li>
);

/** Existing area and Added area legend shown at the top of each open location */
const ContributionLegend: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  return (
    <ul className="flex gap-8 font-mono text-xs">
      <LegendItem className="bg-existing-area">{t('existing-area')}</LegendItem>
      <LegendItem className="bg-blue-700">{t('added-area')}</LegendItem>
    </ul>
  );
};

ContributionLegend.messages = ['containers.map-sidebar-main-panel'];

/** "Loading data..." or the stats error while a stat's request runs or after it fails */
const StatStatusMessage: FCWithMessages<{ status: StatStatus }> = ({ status }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const tUploads = useTranslations('services.uploads');

  if (status === 'success') return null;

  return (
    <p className="pt-3 font-mono text-xs">
      {status === 'loading' ? t('loading-data') : tUploads('general-stats-error')}
    </p>
  );
};

StatStatusMessage.messages = ['containers.map-sidebar-main-panel', 'services.uploads'];

type StatBlockProps = {
  className?: string;
  title: string;
  contribution?: Contribution;
  target?: number;
  status?: StatStatus;
  // Info tooltip at the right of the heading
  tooltip?: ComponentProps<typeof TooltipButton>;
};

/**
 * One section inside a location, with heading and chart, or a loading or error message
 * while its request runs
 */
const StatBlock: FCWithMessages<StatBlockProps> = ({
  className,
  title,
  contribution,
  target,
  status = 'success',
  tooltip,
}) => {
  if (status === 'success' && !contribution) return null;

  return (
    <div className={className}>
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-base font-bold">{title}</h4>
        {tooltip && <TooltipButton side="right" {...tooltip} />}
      </div>
      <StatStatusMessage status={status} />
      {status === 'success' && (
        <ContributionChart className="pt-3" contribution={contribution} target={target} />
      )}
    </div>
  );
};

StatBlock.messages = [
  ...StatStatusMessage.messages,
  ...TooltipButton.messages,
  ...ContributionChart.messages,
];

type HabitatProtectionProps = {
  className?: string;
  status: StatStatus;
  rows: HabitatContribution[];
  tooltip?: ComponentProps<typeof TooltipButton>;
  // If true, shows only "Calculating habitat protection..." instead of specific habitats;
  // used for terrestrial habitats which come from one request and load at once
  loadsAtOnce?: boolean;
};

/**
 * "Habitat Protection" inside a location. Shows once a habitat gains protection,
 * so a shape that adds no habitat protection never shows the section.
 *
 * Marine: Each habitat appears once its request finishes, and a line at the bottom
 * states which habitats are still loading, or says when some failed.
 *
 * Terrestrial: Habitats load at once and show only a "Calculating habitat protection..."
 * line until their results arrive.
 */
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
  // Line about which habitats are still loading
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
            <ul className="pt-3 font-mono text-xs">
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
          <p aria-live="polite" className="pt-3 text-xs empty:hidden">
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
  ...StatStatusMessage.messages,
  ...HabitatContributionList.messages,
  ...HabitatContributionChart.messages,
];

type ContributionItemProps = {
  title: string;
  stats: SectionStats;
  // "Fully/Highly Protected" stat; unset on the terrestrial tab
  fhp?: { status: StatStatus; contribution?: Contribution; tooltip?: StatBlockProps['tooltip'] };
  // "Habitat Protection" rows
  habitats?: Omit<HabitatProtectionProps, 'className'>;
};

/** One collapsible location in the panel: each shows the legend and stats */
const ContributionItem: FCWithMessages<ContributionItemProps> = ({
  title,
  stats,
  fhp,
  habitats,
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const [{ tab }] = useSyncMapContentSettings();
  const tooltips = useDataInfoTooltips([COVERAGE_TOOLTIP_SLUG]);

  return (
    <AccordionItem value={stats.code} className="border-b border-black">
      <AccordionHeader>
        <AccordionTrigger className="group flex w-full items-center justify-between gap-4 py-4 text-left">
          <span className="text-xl font-bold">{title}</span>
          <ChevronDown
            aria-hidden
            className="h-5 w-5 shrink-0 transition-transform duration-300 group-data-[state=open]:rotate-180"
          />
        </AccordionTrigger>
      </AccordionHeader>
      <AccordionContent className="pb-6">
        <ContributionLegend />
        <StatBlock
          className="pt-4"
          title={
            tab === 'marine'
              ? t('marine-conservation-coverage')
              : t('terrestrial-conservation-coverage')
          }
          contribution={stats.coverage}
          target={stats.coverageTarget}
          tooltip={tooltips[COVERAGE_TOOLTIP_SLUG]}
        />
        {fhp && <StatBlock className="pt-6" title={t('fully-highly-protected')} {...fhp} />}
        {habitats && <HabitatProtection className="pt-6" {...habitats} />}
      </AccordionContent>
    </AccordionItem>
  );
};

ContributionItem.messages = [
  'containers.map-sidebar-main-panel',
  ...ContributionLegend.messages,
  ...StatBlock.messages,
  ...HabitatProtection.messages,
];

type ContributionSectionProps = {
  title: string;
  items: ContributionItemProps[];
};

/** One section of the panel: its heading, then one collapsible per location */
const ContributionSection: FCWithMessages<ContributionSectionProps> = ({ title, items }) => (
  <section className="pt-6">
    <h3 className="font-mono text-xs uppercase">{title}</h3>
    {items.map((item) => (
      <ContributionItem key={item.stats.code} {...item} />
    ))}
  </section>
);

ContributionSection.messages = [...ContributionItem.messages];

export default ContributionSection;
