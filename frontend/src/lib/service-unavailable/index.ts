import { isAxiosError } from 'axios';
import type { GetServerSidePropsContext } from 'next';

import ServiceUnavailable from '@/containers/service-unavailable';
import { fetchTranslations } from '@/lib/i18n';

// The backend is unreachable or failing, as opposed to answering with no data (a 404)
export const isBackendDown = (error: unknown) =>
  isAxiosError(error) && (!error.response || error.response.status >= 500);

// MAINTENANCE_MODE only changes the copy; the 503 is only served when the backend is down
export const getServiceUnavailableProps = async (context: GetServerSidePropsContext) => {
  context.res.statusCode = 503;

  return {
    props: {
      serviceUnavailable: { isMaintenance: process.env.MAINTENANCE_MODE === 'true' },
      messages: await fetchTranslations(context.locale, ServiceUnavailable.messages),
    },
  };
};
