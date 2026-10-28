import { useLocale, useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { format } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';

import { MergedPa } from './merge-PAs';

const TERMS_CLASSES = 'font-mono font-bold uppercase';

const UTM_ORIGIN = 'skytruth_progress_tracker';

const protectedPlanetUrl = (pa: MergedPa) => {
  const params = new URLSearchParams({ utm_origin: UTM_ORIGIN });
  if (pa.wdpaPId) params.set('site_pid', pa.wdpaPId);
  return `https://www.protectedplanet.net/${pa.wdpaid}?${params}`;
};

const mpatlasUrl = (pa: MergedPa) =>
  `https://mpatlas.org/zones/${pa.zoneId}/?utm_origin=${UTM_ORIGIN}`;

const PaCard: FCWithMessages<{ pa: MergedPa; showName?: boolean }> = ({ pa, showName = false }) => {
  const t = useTranslations('containers.map');
  const locale = useLocale();

  return (
    <div className="space-y-2">
      {showName && <h3 className="text-xl font-semibold">{pa.name}</h3>}
      <dl className="space-y-2">
        {pa.area != null && (
          <div>
            <dt className={TERMS_CLASSES}>{t('area')}</dt>
            <dd>
              {t('area-km2', {
                area: format({
                  locale,
                  value: pa.area,
                  id: 'formatKM',
                  options: {
                    maximumSignificantDigits: 3,
                  },
                }),
              })}
            </dd>
          </div>
        )}
        {pa.protectionStatus?.name && (
          <div>
            <dt className={TERMS_CLASSES}>{t('type')}</dt>
            <dd
              className={cn('font-semibold', {
                'text-violet': pa.protectionStatus.slug === 'pa',
                'text-green': pa.protectionStatus.slug === 'oecm',
              })}
            >
              {pa.protectionStatus.name}
            </dd>
          </div>
        )}
        {pa.isMarine && (
          <>
            <div>
              <dt className={TERMS_CLASSES}>{t('protection-level')}</dt>
              <dd>{pa.mpaaProtectionLevel ?? t('not-assessed')}</dd>
            </div>
            <div>
              <dt className={TERMS_CLASSES}>{t('establishment-stage')}</dt>
              <dd>{pa.mpaaEstablishmentStage?.name ?? t('n-a')}</dd>
            </div>
          </>
        )}
        {pa.designation && (
          <div>
            <dt className={TERMS_CLASSES}>{t('designation')}</dt>
            <dd>{pa.designation}</dd>
          </div>
        )}
        {pa.year != null && (
          <div>
            <dt className={TERMS_CLASSES}>{t('year')}</dt>
            <dd>{pa.year}</dd>
          </div>
        )}
        <div>
          <dt className={TERMS_CLASSES}>{t('iucn-category')}</dt>
          <dd>{pa.iucnCategory ?? t('n-a')}</dd>
        </div>
        {pa.locations.length > 0 && (
          <div>
            <dt className={TERMS_CLASSES}>{t('location')}</dt>
            <dd>{pa.locations.join(', ')}</dd>
          </div>
        )}
      </dl>
      {pa.mpaaEstablishmentStage?.slug === 'proposed-committed' && (
        <p className="text-xs italic">{t('mpa-not-implemented')}</p>
      )}
      {pa.wdpaid && (
        <a
          href={protectedPlanetUrl(pa)}
          target="_blank"
          rel="noopener noreferrer"
          className="block font-semibold underline"
        >
          {t('view-on-protected-planet')}
        </a>
      )}
      {pa.zoneId && (
        <a
          href={mpatlasUrl(pa)}
          target="_blank"
          rel="noopener noreferrer"
          className="block font-semibold underline"
        >
          {t('view-on-mpatlas')}
        </a>
      )}
    </div>
  );
};

PaCard.messages = ['containers.map'];

export default PaCard;
