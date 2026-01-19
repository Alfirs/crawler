import { PrismaClient } from '@prisma/client';
import { config } from './env.config';
import { logger } from './logger.config';

class Database {
  private prisma: PrismaClient | null = null;
  private connected = false;

  async connect(): Promise<void> {
    // Allow skipping DB in dev when Prisma client/schema is not present
    if (process.env.SKIP_DB === '1') {
      logger.warn('Database connection skipped via SKIP_DB=1');
      return;
    }
    try {
      this.prisma = new PrismaClient({
        datasourceUrl: config.DATABASE_CONNECTION_URI,
      });

      await this.prisma.$connect();
      this.connected = true;
      logger.info('Database connected successfully');
    } catch (error) {
      const message = (error as Error)?.message || '';
      // If Prisma client is not generated, allow app to start without DB
      if (message.includes('did not initialize yet')) {
        logger.warn('Prisma client not generated; skipping DB connection for now');
        return;
      }
      logger.error({ err: error }, 'Database connection failed');
      throw error;
    }
  }

  get client(): PrismaClient {
    if (!this.prisma) {
      throw new Error('Database not connected');
    }
    return this.prisma;
  }

  get isConnected(): boolean {
    return this.connected;
  }

  async disconnect(): Promise<void> {
    if (this.prisma) {
      await this.prisma.$disconnect();
      this.connected = false;
      logger.info('Database disconnected');
    }
  }
}

export const database = new Database();
