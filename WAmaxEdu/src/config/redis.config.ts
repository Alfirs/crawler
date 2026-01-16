import { createClient, RedisClientType } from 'redis';
import { config } from './env.config';
import { logger } from './logger.config';

class Redis {
  private client: RedisClientType | null = null;

  async connect(): Promise<void> {
    // Skip when redis is disabled or we are using memory idempotency store
    if (!config.REDIS_ENABLED || config.IDEMPOTENCY_STORE !== 'redis') {
      logger.info('Redis disabled (using memory store)');
      return;
    }

    try {
      this.client = createClient({
        url: config.REDIS_URI,
        socket: {
          // Avoid endless retries during local dev
          reconnectStrategy: false,
        },
      });

      this.client.on('error', (err) => logger.error({ err }, 'Redis Client Error'));
      this.client.on('connect', () => logger.info('Redis connected'));

      await this.client.connect();
    } catch (error: any) {
      const code = error?.code || '';
      if (code === 'ECONNREFUSED') {
        logger.warn('Redis unavailable, continuing without Redis');
        this.client = null;
        return;
      }
      logger.error({ err: error }, 'Redis connection failed');
      throw error;
    }
  }

  get instance(): RedisClientType {
    if (!this.client) {
      throw new Error('Redis not connected');
    }
    return this.client;
  }

  async disconnect(): Promise<void> {
    if (this.client) {
      await this.client.disconnect();
      logger.info('Redis disconnected');
    }
  }
}

export const redis = new Redis();
