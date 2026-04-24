import { z } from 'zod';

export const SocialAuthRequest = z.object({
  code: z.string().min(1),
  state: z.string().optional(),
  redirectUri: z.string().url(),
});

export type SocialAuthRequest = z.infer<typeof SocialAuthRequest>;
