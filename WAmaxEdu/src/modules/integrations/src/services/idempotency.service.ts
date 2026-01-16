import { createHash } from 'crypto';
import { config } from '@/config/env.config';
import { redis } from '@/config/redis.config';
import { logger } from '@/config/logger.config';

export interface IdempotencyRecord<T> {
  payloadHash: string;
  response: T;
}

const memoryStore: Map<string, { record: IdempotencyRecord<any>; expiresAt: number }> = new Map();

export class IdempotencyService {
  private getRedisClient() {
    try {
      if (config.IDEMPOTENCY_STORE === 'memory') {
        if (config.NODE_ENV === 'production') {
          throw new Error('IDEMPOTENCY_MEMORY_NOT_ALLOWED_IN_PROD');
        }
        return null;
      }
      if (!config.REDIS_ENABLED) {
        throw new Error('REDIS_DISABLED');
      }
      return redis.instance;
    } catch (error) {
      logger.error({ err: error }, 'Redis not available for idempotency');
      throw error;
    }
  }

  private stableStringify(value: any): string {
    if (value === null || typeof value !== 'object') {
      return JSON.stringify(value);
    }

    if (Array.isArray(value)) {
      const items = value.map((item) => this.stableStringify(item));
      return `[${items.join(',')}]`;
    }

    const keys = Object.keys(value).sort();
    const entries = keys.map((key) => `${JSON.stringify(key)}:${this.stableStringify(value[key])}`);
    return `{${entries.join(',')}}`;
  }

  computePayloadHash(payload: unknown): string {
    return createHash('sha256').update(this.stableStringify(payload)).digest('hex');
  }

  async get<T>(key: string): Promise<IdempotencyRecord<T> | null> {
    try {
      const client = this.getRedisClient();
      if (client) {
        const data = await client.get(`idempotency:${key}`);
        return data ? JSON.parse(data) : null;
      }

      const entry = memoryStore.get(key);
      if (entry && entry.expiresAt > Date.now()) {
        return entry.record as IdempotencyRecord<T>;
      }

      memoryStore.delete(key);
      return null;
    } catch (error) {
      logger.error({ err: error }, 'IdempotencyService.get error');
      throw error;
    }
  }

  async set<T>(key: string, value: IdempotencyRecord<T>, ttlSeconds: number): Promise<void> {
    try {
      const client = this.getRedisClient();
      if (client) {
        await client.setEx(`idempotency:${key}`, ttlSeconds, JSON.stringify(value));
        return;
      }

      const expiresAt = Date.now() + ttlSeconds * 1000;
      memoryStore.set(key, { record: value, expiresAt });
    } catch (error) {
      logger.error({ err: error }, 'IdempotencyService.set error');
      throw error;
    }
  }

  async delete(key: string): Promise<void> {
    try {
      const client = this.getRedisClient();
      if (client) {
        await client.del(`idempotency:${key}`);
        return;
      }

      memoryStore.delete(key);
    } catch (error) {
      logger.error({ err: error }, 'IdempotencyService.delete error');
    }
  }
}
