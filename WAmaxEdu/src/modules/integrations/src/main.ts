import express from 'express';
import cors from 'cors';
import compression from 'compression';
import 'express-async-errors';

import { logger } from '@/config/logger.config';
import { config } from '@/config/env.config';
import { redis } from '@/config/redis.config';
import { integrationsRouter } from './controllers/integrations.controller';
import { EventPublisherService } from './services/event-publisher.service';

const app = express();
const eventPublisher = new EventPublisherService();

// Middleware
app.use(compression());
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Health check
app.get('/health', async (req, res) => {
  const redisStatus = await getRedisStatus();
  const brokerStatus = await getBrokerStatus();

  res.json({
    status: 'OK',
    service: 'integrations',
    timestamp: new Date().toISOString(),
    redis: redisStatus,
    broker: brokerStatus,
  });
});

async function getRedisStatus(): Promise<string> {
  if (!config.REDIS_ENABLED) {
    return 'disabled';
  }
  try {
    await redis.connect();
    await redis.instance.ping?.();
    return 'connected';
  } catch (err) {
    logger.error({ err }, 'Redis health check failed');
    return 'error';
  }
}

async function getBrokerStatus(): Promise<string> {
  if (!config.RABBITMQ_ENABLED) {
    return 'disabled';
  }
  try {
    await eventPublisher.ensureConnected();
    return 'connected';
  } catch (err) {
    logger.error({ err }, 'Broker health check failed');
    return 'error';
  }
}

// API routes (spec: /integrations/*)
app.use('/integrations', integrationsRouter);

// Error handling
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  logger.error(err);
  res.status(err.status || 500).json({
    error: {
      code: err.code || 'INTERNAL_ERROR',
      message: err.message || 'Internal server error'
    }
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    error: {
      code: 'NOT_FOUND',
      message: 'Endpoint not found'
    }
  });
});

// Start server (skip when running under tests)
if (process.env.NODE_ENV !== 'test') {
  (async () => {
    try {
      if (config.REDIS_ENABLED) {
        await redis.connect();
      }
      if (config.RABBITMQ_ENABLED) {
        await eventPublisher.ensureConnected();
      }

      const port = process.env.PORT || 3001;
      app.listen(port, () => {
        logger.info(`Integrations Service started on port ${port}`);
      });
    } catch (error) {
      logger.error({ err: error }, 'Failed to start integrations service');
      process.exit(1);
    }
  })();
}

export { app };
