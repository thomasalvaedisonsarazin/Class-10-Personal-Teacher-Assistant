import type { ConfigContext, ExpoConfig } from 'expo/config';

/**
 * Extends app.json. Only the home-Wi-Fi test build (eas.json "preview" profile sets
 * ALLOW_CLEARTEXT_HTTP=true) may call a plain-http backend; store builds stay https-only.
 */
export default ({ config }: ConfigContext): ExpoConfig => {
  const base = config as ExpoConfig;
  if (process.env.ALLOW_CLEARTEXT_HTTP !== 'true') {
    return base;
  }
  return {
    ...base,
    plugins: [...(base.plugins ?? []), ['expo-build-properties', { android: { usesCleartextTraffic: true } }]],
  };
};
