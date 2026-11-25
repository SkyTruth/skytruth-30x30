import { useLocale, useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { formatKM } from '@/lib/utils/formats';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

type ProtectedAreaTextProps = {
  className?: string;
  contribution: Contribution;
  stacked?: boolean;
};

/**
 * "M km² N km² of T km² protected": the added area first, in bold blue, then the protected
 * area including it. `stacked` puts the added area, "N km² of" and "T km² protected" on
 * their own lines
 */
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
        added: (chunks) => (
          <span className={cn('text-xs-bold font-bold text-blue-700', { block: stacked })}>
            {chunks}
          </span>
        ),
        sr: (chunks) => <span className="sr-only">{chunks}</span>,
        total: (chunks) => <span className={cn({ block: stacked })}>{chunks}</span>,
      })}
    </div>
  );
};

ProtectedAreaText.messages = ['components.chart-contribution'];

export default ProtectedAreaText;
