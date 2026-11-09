import { PropsWithChildren } from 'react';

import { ChevronDown } from 'lucide-react';
import { useTranslations } from 'next-intl';

import ContributionChart from '@/components/charts/contribution-chart';
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

/** One legend entry: a colored square (`className` sets its color) and its label */
const LegendItem = ({ className, children }: PropsWithChildren<{ className: string }>) => (
  <li className="flex items-center gap-2">
    <span aria-hidden className={cn('h-2.5 w-2.5', className)} />
    {children}
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
}) => {
  if (status === 'success' && !contribution) return null;

  return (
    <div className={className}>
      <h4 className="text-sm font-bold">{title}</h4>
      <StatStatusMessage status={status} />
      {status === 'success' && (
        <ContributionChart className="pt-3" contribution={contribution} target={target} />
      )}
    </div>
  );
};

StatBlock.messages = [...StatStatusMessage.messages, ...ContributionChart.messages];

type ContributionItemProps = {
  title: string;
  stats: SectionStats;
  // "Fully/Highly Protected" stat; unset on the terrestrial tab
  fhp?: { status: StatStatus; contribution?: Contribution };
};

/** One collapsible location in the panel: each shows the legend and stats */
const ContributionItem: FCWithMessages<ContributionItemProps> = ({ title, stats, fhp }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const [{ tab }] = useSyncMapContentSettings();

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
        />
        {fhp && <StatBlock className="pt-6" title={t('fully-highly-protected')} {...fhp} />}
      </AccordionContent>
    </AccordionItem>
  );
};

ContributionItem.messages = [
  'containers.map-sidebar-main-panel',
  ...ContributionLegend.messages,
  ...StatBlock.messages,
];

type ContributionSectionProps = {
  title: string;
  tooltip?: string;
  items: ContributionItemProps[];
};

/**
 * One section of the panel, the heading with an info tooltip,
 * then one collapsible per location
 */
const ContributionSection: FCWithMessages<ContributionSectionProps> = ({
  title,
  tooltip,
  items,
}) => (
  <section className="pt-6">
    <div className="flex items-center">
      <h3 className="font-mono text-xs uppercase">{title}</h3>
      {tooltip && <TooltipButton className="-mt-1" text={tooltip} />}
    </div>
    {items.map((item) => (
      <ContributionItem key={item.stats.code} {...item} />
    ))}
  </section>
);

ContributionSection.messages = [...ContributionItem.messages, ...TooltipButton.messages];

export default ContributionSection;
