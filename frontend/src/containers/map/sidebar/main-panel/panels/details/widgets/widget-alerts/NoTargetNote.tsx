import { useLocale, useTranslations } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import { FCWithMessages } from '@/types';
import { useGetDataSources } from '@/types/generated/data-source';
import type { LocationGroupsItem } from '@/types/generated/strapi.schemas';

type NoTargetNoteProps = {
  environment: 'marine' | 'terrestrial';
  location: LocationGroupsItem;
};

const NoTargetNote: FCWithMessages<NoTargetNoteProps> = ({ environment, location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  // Codes ending in `*` are country groupings (e.g. FRA*), not single CBD Parties
  const isSingleCountry = location.type === 'country' && !location.code.endsWith('*');

  const { data: sources } = useGetDataSources(
    {
      locale,
      filters: {
        slug: '30x30-targets-general',
      },
    },
    {
      query: {
        enabled: isSingleCountry,
        select: ({ data }) =>
          data.map(({ documentId, slug, title, url }) => ({ documentId, slug, title, url })),
      },
    }
  );

  if (!isSingleCountry) return null;

  return (
    <p className="mt-2 text-xs">
      <span className="relative top-px">
        {environment === 'marine' ? t('no-marine-target') : t('no-terrestrial-target')}
      </span>
      <TooltipButton text="" sources={sources} className="align-bottom hover:bg-transparent" />
    </p>
  );
};

NoTargetNote.messages = ['containers.map-sidebar-main-panel', ...TooltipButton.messages];

export default NoTargetNote;
