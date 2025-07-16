export function mapParamsToSearchParams(mapParams: string | string[] | null): string {
  const params = JSON.parse(mapParams as string);
  const searchParams = new URLSearchParams();

  if (params?.settings) {
    searchParams.set('settings', JSON.stringify(params?.settings || null));
  }

  if (params?.layers) {
    searchParams.set('layers', params?.layers);
  }

  if (params?.layerSettings) {
    searchParams.set('layer-settings', JSON.stringify(params?.layerSettings || null));
  }

  const searchParamsUri = searchParams.toString();

  return decodeURIComponent(searchParamsUri);
}

export default mapParamsToSearchParams;
