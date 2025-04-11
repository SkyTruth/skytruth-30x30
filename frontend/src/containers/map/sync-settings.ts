import { useQueryState, parseAsJson } from 'nuqs';
import { z } from 'zod'
 
export const contentSettingsSchema = z.object({
  showDetails: z.boolean(),
  tab: z.string(),
})

export type ContentSettings = z.infer<typeof contentSettingsSchema>

const DEFAULT_SYNC_CONTENT_SETTINGS: ContentSettings = {
  showDetails: false,
  tab: 'summary',
};

export const useSyncMapContentSettings = () => {
  return useQueryState(
    'content',
    parseAsJson<ContentSettings>(contentSettingsSchema.parse).withDefault(DEFAULT_SYNC_CONTENT_SETTINGS)
  );
};
