import { useTranslations } from 'next-intl';

import { FCWithMessages } from '@/types';
import type { LocationGroupsItem } from '@/types/generated/strapi.schemas';

type NoTargetNoteProps = {
  environment: 'marine' | 'terrestrial';
  location: LocationGroupsItem;
};

const NoTargetNote: FCWithMessages<NoTargetNoteProps> = ({ environment, location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  // Codes ending in `*` are country groupings (e.g. FRA*), not single CBD Parties
  const isSingleCountry = location.type === 'country' && !location.code.endsWith('*');
  if (!isSingleCountry) return null;

  return (
    <p className="mt-2 text-xs">
      {environment === 'marine' ? t('no-marine-target') : t('no-terrestrial-target')}
    </p>
  );
};

NoTargetNote.messages = ['containers.map-sidebar-main-panel'];

export default NoTargetNote;
