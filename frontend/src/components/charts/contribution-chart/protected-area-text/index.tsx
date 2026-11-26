import { useLocale, useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { formatKM } from '@/lib/utils/formats';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

type ProtectedAreaTextProps = {
  className?: string;
  contribution: Contribution;
  // Puts "T km² protected" on its own line
  stacked?: boolean;
};

const ProtectedAreaText: FCWithMessages<ProtectedAreaTextProps> = ({
  className,
  contribution: { existing, added, total },
  stacked = false,
}) => {
  const t = useTranslations('components.chart-contribution');
  const locale = useLocale();

  return (
    <div className={cn('text-xs', className)}>
      {t.rich('protected-area', {
        protectedArea: formatKM(locale, existing + added),
        addedArea: formatKM(locale, added),
        totalArea: formatKM(locale, total),
        added: (chunks) => <span className="text-xs-bold font-bold text-blue-700">{chunks}</span>,
        total: (chunks) => <span className={cn({ block: stacked })}>{chunks}</span>,
      })}
    </div>
  );
};

ProtectedAreaText.messages = ['components.chart-contribution'];

export default ProtectedAreaText;
