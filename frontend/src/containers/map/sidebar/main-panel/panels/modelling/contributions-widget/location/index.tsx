import { ChevronDown } from 'lucide-react';
import { useTranslations } from 'next-intl';

import {
  AccordionContent,
  AccordionHeader,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useDataInfoTooltips from '@/hooks/use-data-info-tooltips';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

import HabitatProtection, { HabitatProtectionProps } from '../habitat-protection';
import ContributionLegend from '../legend';
import StatBlock, { StatBlockProps } from '../stat-block';
import type { StatStatus } from '../stat-status';
import { SectionStats } from '../use-coverage-contributions';

// Shared with the Progress Tracker's coverage widgets
const COVERAGE_TOOLTIP_SLUG = 'coverage-widget';

type ContributionLocationProps = {
  title: string;
  stats: SectionStats;
  fhp?: { status: StatStatus; contribution?: Contribution; tooltip?: StatBlockProps['tooltip'] };
  habitats?: Omit<HabitatProtectionProps, 'className'>;
};

const ContributionLocation: FCWithMessages<ContributionLocationProps> = ({
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

ContributionLocation.messages = [
  'containers.map-sidebar-main-panel',
  ...ContributionLegend.messages,
  ...StatBlock.messages,
  ...HabitatProtection.messages,
];

export default ContributionLocation;
