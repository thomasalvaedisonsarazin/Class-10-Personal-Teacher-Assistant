import { existsSync } from 'node:fs';

import type { ConfigContext, ExpoConfig } from 'expo/config';

/**
 * Extends app.json.
 * - Firebase (Android push): EAS builds get google-services.json from the GOOGLE_SERVICES_JSON
 *   file variable; local builds use ./google-services.json (gitignored).
 * - Only the home-Wi-Fi test build (eas.json "preview" profile sets ALLOW_CLEARTEXT_HTTP=true)
 *   may call a plain-http backend; store builds stay https-only.
 */
export default ({ config }: ConfigContext): ExpoConfig => {
  const base = config as ExpoConfig;
  const googleServicesFile =
    process.env.GOOGLE_SERVICES_JSON ?? (existsSync('./google-services.json') ? './google-services.json' : undefined);
  const plugins = [...(base.plugins ?? [])];
  if (process.env.ALLOW_CLEARTEXT_HTTP === 'true') {
    plugins.push(['expo-build-properties', { android: { usesCleartextTraffic: true } }]);
  }
  return {
    ...base,
    android: { ...base.android, ...(googleServicesFile ? { googleServicesFile } : {}) },
    plugins,
  };
};
