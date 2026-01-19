import { config } from '@/config/env.config';

export class IntegrationsConfig {
  static get idempotencyTTL(): number {
    return config.INTEGRATIONS_IDEMPOTENCY_TTL;
  }

  static get webhookSecret(): string | undefined {
    return config.INTEGRATIONS_WEBHOOK_SECRET;
  }

  static get supportedChannels(): string[] {
    return ['WHATSAPP'];
  }

  static get maxRetries(): number {
    return 5;
  }

  static get retryDelayMs(): number {
    return 1000; // Exponential backoff starting point
  }
}
