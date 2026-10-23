import { useTranslations } from 'next-intl';

import { FCWithMessages } from '@/types';

import CardAccordion from '../CardAccordion';

import {
  useClickedProtectedAreas,
  useMergedProtectedAreas,
  useProtectedAreaRecords,
} from './hooks';
import PaCard from './PaCard';

const ProtectedAreaPopup: FCWithMessages<{ layerSlug: string }> = () => {
  const t = useTranslations('containers.map');

  const clicked = useClickedProtectedAreas();
  const { rows, isFetching } = useProtectedAreaRecords(clicked);
  const mergedPas = useMergedProtectedAreas(clicked, rows);

  if (!clicked.length) return null;

  return (
    <div className="flex flex-col gap-2">
      {isFetching && <div className="my-4 text-center font-mono text-xl">{t('loading')}</div>}
      {!isFetching && !mergedPas.length && (
        <div className="my-4 text-center font-mono">{t('no-data-available')}</div>
      )}
      {!isFetching && mergedPas.length === 1 && <PaCard pa={mergedPas[0]} showName />}
      {!isFetching && mergedPas.length > 1 && (
        <CardAccordion
          items={mergedPas.map((pa) => ({
            id: pa.id,
            title: pa.name,
            content: <PaCard pa={pa} />,
          }))}
        />
      )}
    </div>
  );
};

ProtectedAreaPopup.messages = [
  ...PaCard.messages,
  // Required by the `useLocationName` hook
  'locations',
];

export default ProtectedAreaPopup;
