import { config as loadEnv } from 'dotenv';
import { z } from 'zod';

loadEnv();

const booleanString = z.union([z.boolean(), z.string()]).transform((value) => {
  if (typeof value === 'string') {
    return !['false', '0', '', 'no', 'off'].includes(value.toLowerCase());
  }
  return Boolean(value);
});

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  PORT: z.coerce.number().default(3000),

  // Database
  DATABASE_PROVIDER: z.enum(['postgresql', 'mysql']).default('postgresql'),
  DATABASE_CONNECTION_URI: z.string().min(1).default('postgres://localhost:5432/dev'),
  MESSAGE_STORE: z.enum(['database', 'memory']).default('memory'),

  // Redis
  REDIS_ENABLED: booleanString.default(false),
  REDIS_URI: z.string().default('redis://localhost:6379'),
  IDEMPOTENCY_STORE: z.enum(['redis', 'memory']).default('memory'),

  // Auth
  JWT_SECRET: z.string().min(1).default('dev-placeholder-jwt'),
  API_KEY_SECRET: z.string().min(1).default('dev-placeholder-api-key'),
  AUTH_REQUIRED: booleanString.default(false),
  AUTH_TOKEN_TTL_SECONDS: z.coerce.number().default(3600),

  // Integrations
  INTEGRATIONS_IDEMPOTENCY_TTL: z.coerce.number().default(86400), // 24 hours
  INTEGRATIONS_WEBHOOK_SECRET: z.string().optional(),
  WHATSAPP_PROVIDER_BASE_URL: z.string().optional(),
  WHATSAPP_PROVIDER_API_KEY: z.string().optional(),
  WHATSAPP_PROVIDER_WEBHOOK_URL: z.string().optional(),
  WHATSAPP_PROVIDER_WEBHOOK_EVENTS: z.string().optional(),
  WHATSAPP_PROVIDER_WEBHOOK_BY_EVENTS: booleanString.default(false),
  WHATSAPP_PROVIDER_TIMEOUT_MS: z.coerce.number().default(15000),
  EVOLUTION_INSTANCE_NAME: z.string().default('wamaxedu'),

  // Bitrix24
  BITRIX24_PORTAL_URL: z.string().optional(),
  BITRIX24_WEBHOOK_URL: z.string().optional(),
  BITRIX24_CONNECTOR_ID: z.string().default('wamaxedu_whatsapp_dev'),
  BITRIX24_TEST_LINE_ID: z.string().optional(),

  // Event broker (RabbitMQ)
  RABBITMQ_ENABLED: booleanString.default(false),
  RABBITMQ_URI: z.string().optional(),
  MESSAGES_BROKER_QUEUE: z.string().default('messages.service'),
  REALTIME_BROKER_QUEUE: z.string().default('realtime.gateway'),
  BROKER_MAX_RETRIES: z.coerce.number().default(3),
  BROKER_RETRY_DELAY_MS: z.coerce.number().default(5000),
  BROKER_PREFETCH: z.coerce.number().default(10),

  // Logging
  LOG_LEVEL: z.enum(['error', 'warn', 'info', 'debug']).default('info'),
});

export const config = envSchema.parse(process.env);
